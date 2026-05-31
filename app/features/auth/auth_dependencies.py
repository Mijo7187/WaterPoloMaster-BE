# ============================================
# AUTH DEPENDENCIES - FastAPI Dependencies
# ============================================
# This file contains reusable FastAPI dependencies for authentication
# Dependencies run BEFORE your endpoint and provide validated data
#
# Think of them as "middleware" that runs per-route
# 
# USAGE:
# @router.get("/protected", dependencies=[Depends(get_current_user)])
# def protected_route(user = Depends(get_current_user)):
#     # user is already validated and fetched from database
#     return {"user": user.email}
# ============================================

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.core.db.database import get_db
from app.core.api.exceptions import UnauthorizedException, ForbiddenException
from app.core.security import decode_access_token
from app.core.redis import get_access_token
from app.features.users.users_models import User, UserRole
from app.features.users.users_repository import UserRepository


# ============================================
# SECURITY SCHEME
# ============================================
# HTTPBearer handles "Authorization: Bearer <token>" header
# Automatically extracts token from request
security = HTTPBearer()


# ============================================
# DEPENDENCY: GET CURRENT USER
# ============================================
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get current authenticated user
    
    How it works:
    1. Extract token from Authorization header (HTTPBearer does this)
    2. Decode and verify JWT token
    3. Get user from database
    4. Return user object
    
    Args:
        credentials: Auto-extracted from "Authorization: Bearer <token>" header
        db: Database session
        
    Returns:
        User object if authenticated
        
    Raises:
        HTTPException 401: If token invalid or user not found
        
    Example usage in endpoint:
        @router.get("/me")
        async def get_me(current_user: User = Depends(get_current_user)):
            return {"email": current_user.email}
    """
    # Extract token from credentials
    token = credentials.credentials
    
    # Decode token to get user email
    payload = decode_access_token(token)
    
    if payload is None:
        raise UnauthorizedException("Invalid authentication credentials")
    
    # Get user email from token
    user_email: str = payload.get("sub")
    
    if user_email is None:
        raise UnauthorizedException("Invalid token payload")
    
    # Check token type (should be "access")
    token_type: str = payload.get("type")
    if token_type != "access":
        raise UnauthorizedException("Invalid token type. Use access token.")
    
    # Get user_id from token and verify against Redis
    user_id: int = payload.get("user_id")
    if user_id is None:
        raise UnauthorizedException("Invalid token payload")
    
    stored_token = get_access_token(user_id)
    if stored_token != token:
        raise UnauthorizedException("Token has been revoked or expired")

    # Get user from database
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_email(user_email)

    if user is None:
        raise UnauthorizedException("User not found")

    return user


# ============================================
# DEPENDENCY: GET CURRENT ACTIVE USER
# ============================================
async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    FastAPI dependency to get current ACTIVE user
    
    Builds on get_current_user() and adds active check
    
    Args:
        current_user: User from get_current_user dependency
        
    Returns:
        User object if active
        
    Raises:
        HTTPException 403: If user is inactive/suspended
        
    Example usage:
        @router.get("/dashboard")
        async def dashboard(user: User = Depends(get_current_active_user)):
            # User is authenticated AND active
            return {"message": f"Welcome {user.username}"}
    """
    if not current_user.is_active:
        raise ForbiddenException("Inactive user. Account may be suspended.")
    
    return current_user


# ============================================
# DEPENDENCY: REQUIRE ADMIN
# ============================================
async def require_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    FastAPI dependency to require admin/superuser access
    
    Builds on get_current_active_user() and adds admin check
    
    Args:
        current_user: User from get_current_active_user dependency
        
    Returns:
        User object if user is admin
        
    Raises:
        HTTPException 403: If user is not admin
        
    Example usage:
        @router.delete("/users/{user_id}")
        async def delete_user(
            user_id: int,
            admin: User = Depends(require_admin)
        ):
            # Only admins can reach this endpoint
            # Delete user logic...
            return {"message": "User deleted"}
            
    Alternative usage (no need for user object):
        @router.post("/admin-action", dependencies=[Depends(require_admin)])
        async def admin_action():
            # Admin check runs, but we don't need user object
            return {"message": "Admin action completed"}
    """
    if UserRole.ADMIN not in (current_user.roles or []):
        raise ForbiddenException("Admin access required. Insufficient permissions.")
    
    return current_user


# ============================================
# OPTIONAL: GET CURRENT USER (OPTIONAL)
# ============================================
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    FastAPI dependency to optionally get current user
    
    Unlike get_current_user(), this does NOT raise error if no token
    Useful for endpoints that work both authenticated and unauthenticated
    
    Args:
        credentials: Optional token from header
        db: Database session
        
    Returns:
        User object if authenticated, None if not
        
    Example usage:
        @router.get("/products")
        async def get_products(user: Optional[User] = Depends(get_current_user_optional)):
            if user:
                # Show personalized products
                return {"products": [...], "user": user.email}
            else:
                # Show generic products
                return {"products": [...]}
    """
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        
        if payload is None:
            return None
        
        user_email = payload.get("sub")
        if user_email is None:
            return None
        
        user_repo = UserRepository(db)
        user = user_repo.get_user_by_email(user_email)
        
        return user
        
    except Exception:
        return None


# ============================================
# USAGE EXAMPLES:
# ============================================
#
# 1. PROTECTED ROUTE (requires authentication):
#    @router.get("/profile")
#    async def get_profile(user: User = Depends(get_current_user)):
#        return {"email": user.email}
#
# 2. ACTIVE USER ONLY:
#    @router.post("/create-post")
#    async def create_post(user: User = Depends(get_current_active_user)):
#        # Only active users can create posts
#        return {"message": "Post created"}
#
# 3. ADMIN ONLY:
#    @router.delete("/users/{id}")
#    async def delete_user(id: int, admin: User = Depends(require_admin)):
#        # Only admins can delete users
#        return {"message": "User deleted"}
#
# 4. ADMIN CHECK WITHOUT USER OBJECT:
#    @router.post("/admin-action", dependencies=[Depends(require_admin)])
#    async def admin_action():
#        # Admin check runs, but endpoint doesn't need user object
#        return {"message": "Done"}
#
# 5. OPTIONAL AUTH:
#    @router.get("/posts")
#    async def get_posts(user: Optional[User] = Depends(get_current_user_optional)):
#        if user:
#            # Show personalized posts
#        else:
#            # Show public posts
# ============================================
