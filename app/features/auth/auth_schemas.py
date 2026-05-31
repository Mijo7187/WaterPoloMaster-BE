# ============================================
# AUTH SCHEMAS - Authentication Data Models
# ============================================
# This file defines data structures for authentication
# - Login requests
# - Token responses
# - Refresh token requests
# ============================================

from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# ============================================
# LOGIN REQUEST SCHEMA
# ============================================
class LoginRequest(BaseModel):
    """
    Schema for user login
    User provides email and password
    
    Example:
    {
        "email": "user@example.com",
        "password": "mypassword123"
    }
    """
    email: EmailStr  # Email validation automatic
    password: str = Field(..., min_length=3)
    
    # Configuration for Pydantic v2
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                  "email": "test@test.com",
                  "password": "test"
                }
            ]
        }
    }


# ============================================
# TOKEN RESPONSE SCHEMA
# ============================================
class TokenResponse(BaseModel):
    """
    Schema for token response after successful login
    
    Returns both access and refresh tokens
    - access_token: Short-lived (30 min), used for API requests
    - refresh_token: Long-lived (7 days), used to get new access tokens
    
    Example response:
    {
        "access_token": "eyJhbGci...",
        "refresh_token": "eyJhbGci...",
        "token_type": "bearer"
    }
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # Standard OAuth2 token type
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer"
                }
            ]
        }
    }


# ============================================
# REFRESH TOKEN REQUEST SCHEMA
# ============================================
class RefreshTokenRequest(BaseModel):
    """
    Schema for refresh token request
    User sends refresh token to get a new access token
    
    Example:
    {
        "refresh_token": "eyJhbGci..."
    }
    """
    refresh_token: str = Field(..., description="Valid refresh token")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                }
            ]
        }
    }


# ============================================
# USAGE FLOW:
# ============================================
# 1. LOGIN:
#    POST /auth/login
#    Body: LoginRequest {"email": "...", "password": "..."}
#    Response: TokenResponse {access_token, refresh_token, token_type}
#
# 2. USE ACCESS TOKEN:
#    GET /protected-endpoint
#    Header: Authorization: Bearer <access_token>
#
# 3. WHEN ACCESS TOKEN EXPIRES:
#    POST /auth/refresh
#    Body: RefreshTokenRequest {"refresh_token": "..."}
#    Response: TokenResponse {new_access_token, new_refresh_token, token_type}
# ============================================
