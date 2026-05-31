# ============================================
# AUTH SERVICE - Authentication Business Logic
# ============================================
# This file handles authentication logic:
# - Verify user credentials
# - Create access and refresh tokens
# - Validate refresh tokens
# - Token refresh logic
# ============================================

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Tuple
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import verify_password, decode_access_token
from app.core.redis import store_access_token, store_refresh_token, get_refresh_token, delete_user_tokens
from app.features.users.users_models import User
from app.features.users.users_repository import UserRepository


# ============================================
# AUTH SERVICE CLASS
# ============================================
class AuthService:
    """
    Service for authentication operations
    Handles login, token creation, and token refresh
    """
    
    def __init__(self, db: Session):
        """
        Initialize auth service with database session
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.user_repository = UserRepository(db)
    
    # ============================================
    # AUTHENTICATE USER (Login)
    # ============================================
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """
        Verify user credentials
        
        Steps:
        1. Find user by email
        2. Check if user exists and is active
        3. Verify password
        
        Args:
            email: User's email
            password: Plain text password
            
        Returns:
            User object if authentication successful, None otherwise
            
        Example:
            user = auth_service.authenticate_user("admin@example.com", "password123")
            if user:
                # Login successful
            else:
                # Invalid credentials
        """
        # Find user by email
        user = self.user_repository.get_user_by_email(email)
        
        # Check if user exists
        if not user:
            return None
        
        # Check if user is active
        if not user.is_active:
            return None
        
        # Verify password
        if not verify_password(password, user.hashed_password):
            return None
        
        # Authentication successful
        return user
    
    # ============================================
    # CREATE ACCESS TOKEN
    # ============================================
    def create_access_token(self, user: User) -> str:
        """
        Create JWT access token for user
        
        Access tokens are short-lived (default: 30 minutes)
        Used for API authentication
        
        Args:
            user: User object
            
        Returns:
            JWT access token string
            
        Example:
            token = auth_service.create_access_token(user)
            # "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        """
        # Calculate expiration time
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.now(timezone.utc) + expires_delta
        
        # Prepare token data
        token_data = {
            "sub": user.email,  # Subject (user identifier)
            "user_id": user.id,  # Additional user info
            "roles": user.roles,  # User roles list
            "exp": expire,  # Expiration time
            "type": "access"  # Token type
        }
        
        # Create and return JWT
        encoded_jwt = jwt.encode(
            token_data,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return encoded_jwt
    
    # ============================================
    # CREATE REFRESH TOKEN
    # ============================================
    def create_refresh_token(self, user: User) -> str:
        """
        Create JWT refresh token for user
        
        Refresh tokens are long-lived (default: 7 days)
        Used to obtain new access tokens without re-login
        
        Args:
            user: User object
            
        Returns:
            JWT refresh token string
            
        Example:
            refresh_token = auth_service.create_refresh_token(user)
            # "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        """
        # Calculate expiration time (7 days)
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        expire = datetime.now(timezone.utc) + expires_delta
        
        # Prepare token data (minimal info for security)
        token_data = {
            "sub": user.email,
            "user_id": user.id,
            "exp": expire,
            "type": "refresh"  # Mark as refresh token
        }
        
        # Create and return JWT
        encoded_jwt = jwt.encode(
            token_data,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return encoded_jwt
    
    # ============================================
    # CREATE BOTH TOKENS
    # ============================================
    def create_tokens(self, user: User) -> Dict[str, str]:
        """
        Create both access and refresh tokens
        
        Args:
            user: User object
            
        Returns:
            Dictionary with access_token and refresh_token
            
        Example:
            tokens = auth_service.create_tokens(user)
            # {"access_token": "...", "refresh_token": "..."}
        """
        access_token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user)
        
        # Store both tokens in Redis
        store_access_token(user.id, access_token)
        store_refresh_token(user.id, refresh_token)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    
    # ============================================
    # VERIFY REFRESH TOKEN
    # ============================================
    def verify_refresh_token(self, refresh_token: str) -> Optional[Dict]:
        """
        Verify and decode refresh token
        
        Args:
            refresh_token: JWT refresh token string
            
        Returns:
            Token payload if valid, None otherwise
            
        Example:
            payload = auth_service.verify_refresh_token(token)
            if payload:
                # Token valid
                user_email = payload["sub"]
        """
        try:
            # Decode token
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            
            # Check if it's a refresh token
            if payload.get("type") != "refresh":
                return None
            
            return payload
            
        except JWTError:
            # Token invalid (expired, tampered, etc.)
            return None
    
    # ============================================
    # REFRESH ACCESS TOKEN
    # ============================================
    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """
        Generate new access token from refresh token
        
        Steps:
        1. Verify refresh token
        2. Get user from database
        3. Create new access token (and optionally new refresh token)
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            Dictionary with new tokens if successful, None otherwise
            
        Example:
            new_tokens = auth_service.refresh_access_token(old_refresh_token)
            if new_tokens:
                # Use new_tokens["access_token"]
        """
        # Verify refresh token
        payload = self.verify_refresh_token(refresh_token)
        if not payload:
            return None
        
        # Get user info from token
        user_email: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        if not user_email or not user_id:
            return None
        
        # Check if refresh token matches what's stored in Redis
        stored_refresh = get_refresh_token(user_id)
        if stored_refresh != refresh_token:
            return None
        
        # Get user from database
        user = self.user_repository.get_user_by_email(user_email)
        if not user or not user.is_active:
            return None
        
        # Create new tokens (stores them in Redis)
        return self.create_tokens(user)
    
    # ============================================
    # LOGOUT - Remove tokens from Redis
    # ============================================
    @staticmethod
    def logout(user_id: int) -> None:
        """
        Logout user by removing all tokens from Redis
        
        Args:
            user_id: ID of the user to logout
        """
        delete_user_tokens(user_id)


# ============================================
# USAGE EXAMPLE:
# ============================================
# auth_service = AuthService(db)
#
# # LOGIN:
# user = auth_service.authenticate_user("user@example.com", "password123")
# if user:
#     tokens = auth_service.create_tokens(user)
#     # Return tokens to client
#
# # REFRESH:
# new_tokens = auth_service.refresh_access_token(old_refresh_token)
# if new_tokens:
#     # Return new tokens to client
# ============================================
