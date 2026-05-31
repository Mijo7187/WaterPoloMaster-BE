# ============================================
# SECURITY - Security Utilities
# ============================================
# This file contains security-related functions
# - Password hashing and verification
# - JWT token creation and verification
# - User authentication helpers
#
# SECURITY BEST PRACTICES:
# - Never store plain text passwords
# - Use bcrypt for password hashing
# - Use JWT for authentication tokens
# - Keep SECRET_KEY secret!
# ============================================

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import bcrypt

from app.core.config import settings


# ============================================
# PASSWORD FUNCTIONS
# ============================================

def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt
    
    SECURITY: Always hash passwords before storing!
    Never store plain text passwords in database
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password (safe to store in database)
        
    Example:
        plain = "mypassword123"
        hashed = hash_password(plain)
        # hashed = "$2b$12$KIX..."
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify if plain password matches hashed password
    
    Used during login to check if password is correct
    
    Args:
        plain_password: Password user entered
        hashed_password: Hashed password from database
        
    Returns:
        True if passwords match, False otherwise
        
    Example:
        plain = "mypassword123"
        hashed = "$2b$12$KIX..."  # From database
        is_valid = verify_password(plain, hashed)
        # is_valid = True
    """
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# ============================================
# JWT TOKEN FUNCTIONS
# ============================================

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    JWT (JSON Web Token) is used for authentication
    - User logs in → receives token
    - User sends token with each request
    - Server validates token to identify user
    
    Args:
        data: Dictionary of data to encode in token (usually user info)
        expires_delta: How long token is valid (optional)
        
    Returns:
        JWT token string
        
    Example:
        token_data = {"sub": "user@example.com", "user_id": 1}
        token = create_access_token(token_data)
        # token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    """
    # Copy data to avoid modifying original
    to_encode = data.copy()
    
    # Calculate expiration time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Use default from settings (usually 30 minutes)
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add expiration to token data
    to_encode.update({"exp": expire})
    
    # Create and return JWT token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,  # Secret key from .env
        algorithm=settings.ALGORITHM  # Usually "HS256"
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT token
    
    Used to validate tokens sent by users
    
    Args:
        token: JWT token string
        
    Returns:
        Dictionary with token data if valid, None if invalid
        
    Example:
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        payload = decode_access_token(token)
        # payload = {"sub": "user@example.com", "user_id": 1, "exp": ...}
    """
    try:
        # Decode the token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    
    except JWTError:
        # Token is invalid (expired, tampered, etc.)
        return None


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_user_email_from_token(token: str) -> Optional[str]:
    """
    Extract user email from JWT token
    
    JWT tokens usually contain user identifier in "sub" field
    
    Args:
        token: JWT token string
        
    Returns:
        User email if token valid, None otherwise
        
    Example:
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        email = get_user_email_from_token(token)
        # email = "user@example.com"
    """
    payload = decode_access_token(token)
    
    if payload is None:
        return None
    
    # "sub" (subject) is the standard JWT field for user identifier
    email: str = payload.get("sub")
    return email


# ============================================
# USAGE EXAMPLE (Login Flow):
# ============================================
# 1. User registers:
#    plain_password = "mypassword123"
#    hashed = hash_password(plain_password)
#    # Store 'hashed' in database
#
# 2. User logs in:
#    entered_password = "mypassword123"
#    db_hashed = user.hashed_password  # From database
#    if verify_password(entered_password, db_hashed):
#        # Password correct, create token
#        token = create_access_token({"sub": user.email})
#        # Send token to user
#
# 3. User makes authenticated request:
#    # User sends token in header: Authorization: Bearer <token>
#    email = get_user_email_from_token(token)
#    if email:
#        # Token valid, user authenticated
#        user = db.query(User).filter(User.email == email).first()
#        # Process request for this user
# ============================================
