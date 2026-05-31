# ============================================
# AUTH ROUTER - Authentication Endpoints
# ============================================
# This file defines authentication API endpoints:
# - POST /auth/login - User login
# - POST /auth/refresh - Refresh access token
# - GET /auth/me - Get current user info
# ============================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db.database import get_db
from app.core.api.exceptions import UnauthorizedException
from app.core.api.responses import success_response
from app.features.auth.auth_schemas import LoginRequest, RefreshTokenRequest
from app.features.auth.auth_service import AuthService
from app.features.auth.auth_dependencies import get_current_active_user
from app.features.users.users_models import User
from app.features.users.users_schemas import UserResponse


# ============================================
# CREATE ROUTER
# ============================================
router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


# ============================================
# ENDPOINT 1: LOGIN
# ============================================
@router.post("/login")
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    User login endpoint
    
    Authenticates user and returns JWT tokens
    
    **Request Body:**
    - email: User's email address
    - password: User's password
    
    **Response:**
    - access_token: Short-lived token (30 min) for API requests
    - refresh_token: Long-lived token (7 days) to get new access tokens
    - token_type: "bearer" (standard OAuth2 type)
    
    **Example Request:**
    ```json
    POST /auth/login
    {
        "email": "test@test.com",
        "password": "test"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer"
    }
    ```
    
    **Errors:**
    - 401: Invalid email or password
    - 403: User account is inactive
    """
    # Create auth service
    auth_service = AuthService(db)

    # Authenticate user
    user = auth_service.authenticate_user(
        email=login_data.email,
        password=login_data.password
    )

    # Check if authentication failed
    if not user:
        raise UnauthorizedException("Incorrect email or password")

    # Create tokens
    tokens = auth_service.create_tokens(user)

    # Return token response
    return success_response(
        data={
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "user_id": user.id,
            "roles": user.roles,
            "company_id": user.company_id,
        },
        messages=["Login successful"],
    )


# ============================================
# ENDPOINT 2: REFRESH TOKEN
# ============================================
@router.post("/refresh")
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token endpoint
    
    Get new access token using refresh token
    (without requiring user to log in again)
    
    **Request Body:**
    - refresh_token: Valid refresh token from login
    
    **Response:**
    - access_token: New short-lived access token
    - refresh_token: New refresh token
    - token_type: "bearer"
    
    **Example Request:**
    ```json
    POST /auth/refresh
    {
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```
    
    **Example Response:**
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer"
    }
    ```
    
    **Errors:**
    - 401: Invalid or expired refresh token
    - 401: User not found or inactive
    
    **Usage Flow:**
    1. User logs in → receives access_token + refresh_token
    2. User makes API requests with access_token
    3. Access token expires after 30 minutes
    4. User calls /auth/refresh with refresh_token
    5. Receives new access_token (and new refresh_token)
    6. Continues making API requests
    """
    # Create auth service
    auth_service = AuthService(db)

    # Refresh tokens
    new_tokens = auth_service.refresh_access_token(refresh_data.refresh_token)

    # Check if refresh failed
    if not new_tokens:
        raise UnauthorizedException("Invalid or expired refresh token")

    # Return new tokens
    return success_response(
        data={
            "access_token": new_tokens["access_token"],
            "refresh_token": new_tokens["refresh_token"],
            "token_type": "bearer",
        },
        messages=["Token refreshed"],
    )


# ============================================
# ENDPOINT 3: GET CURRENT USER (ME)
# ============================================
@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current authenticated user information
    
    Returns information about the currently logged-in user
    Requires valid access token in Authorization header
    
    **Headers Required:**
    - Authorization: Bearer <access_token>
    
    **Response:**
    - User information (id, email, username, etc.)
    
    **Example Request:**
    ```
    GET /auth/me
    Headers:
        Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    ```
    
    **Example Response:**
    ```json
    {
        "id": 1,
        "email": "admin@waterpolo.com",
        "username": "admin",
        "full_name": "Admin User",
        "is_active": true,
        "is_superuser": true,
        "created_at": "2024-01-01T12:00:00Z"
    }
    ```
    
    **Errors:**
    - 401: No token provided or invalid token
    - 403: User account is inactive
    
    **Usage:**
    Use this endpoint to:
    - Verify token is still valid
    - Get updated user information
    - Check user permissions (is_superuser)
    """
    return success_response(
        data=UserResponse.model_validate(current_user).model_dump(),
        message="Current user",
    )


# ============================================
# ENDPOINT 4: LOGOUT
# ============================================
@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_active_user)
):
    """
    Logout endpoint - revokes all tokens for the current user
    
    Removes access and refresh tokens from Redis,
    effectively invalidating the user's session.
    
    **Headers Required:**
    - Authorization: Bearer <access_token>
    
    **Errors:**
    - 401: No token provided or invalid token
    """
    AuthService.logout(current_user.id)
    return success_response(messages=["Successfully logged out"])


# ============================================
# AUTHENTICATION FLOW DOCUMENTATION
# ============================================
#
# TYPICAL FLOW:
#
# 1. USER REGISTRATION (use /users endpoint):
#    POST /users/
#    {
#        "email": "newuser@example.com",
#        "username": "newuser",
#        "password": "password123"
#    }
#
# 2. USER LOGIN:
#    POST /auth/login
#    {
#        "email": "newuser@example.com",
#        "password": "password123"
#    }
#    Response: {access_token, refresh_token}
#
# 3. MAKE AUTHENTICATED REQUESTS:
#    GET /protected-endpoint
#    Headers:
#        Authorization: Bearer <access_token>
#
# 4. WHEN ACCESS TOKEN EXPIRES (after 30 min):
#    POST /auth/refresh
#    {
#        "refresh_token": "<refresh_token>"
#    }
#    Response: {new_access_token, new_refresh_token}
#
# 5. CHECK CURRENT USER:
#    GET /auth/me
#    Headers:
#        Authorization: Bearer <access_token>
#
# ============================================
