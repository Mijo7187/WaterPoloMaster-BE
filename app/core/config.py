# ============================================
# CONFIG - Application Configuration
# ============================================
# This file loads settings from .env file
# Uses Pydantic Settings for type validation
#
# WHY THIS FILE?
# - All settings in one place
# - Type-safe (Pydantic validates types)
# - Easy to change environment (dev/prod)
# - Loads from .env automatically
# ============================================

from pydantic_settings import BaseSettings
from typing import Optional


# ============================================
# SETTINGS CLASS
# ============================================
class Settings(BaseSettings):
    """
    Application settings loaded from .env file
    
    Pydantic automatically:
    - Loads from .env file
    - Validates data types
    - Provides default values
    """
    
    # ============================================
    # APPLICATION SETTINGS
    # ============================================
    APP_ENV: str = "development"  # development, production, testing
    APP_NAME: str = "WaterPoloMaster"
    API_VERSION: str = "v1"
    
    # ============================================
    # DATABASE SETTINGS
    # ============================================
    DATABASE_URL: str
    # Example formats:
    # SQLite: sqlite:///./waterpolo.db
    # PostgreSQL: postgresql://user:password@localhost:5432/dbname
    # MySQL: mysql+pymysql://user:password@localhost:3306/dbname
    
    # ============================================
    # SECURITY SETTINGS
    # ============================================
    SECRET_KEY: str  # Secret key for JWT tokens (keep this SECRET!)
    ALGORITHM: str = "HS256"  # Algorithm for JWT encoding
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Access token expiration (30 minutes)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # Refresh token expiration (7 days)
    
    # ============================================
    # REDIS SETTINGS
    # ============================================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # ============================================
    # SERVER SETTINGS
    # ============================================
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True  # Auto-reload on code changes (dev only)
    
    # ============================================
    # PYDANTIC CONFIGURATION
    # ============================================
    class Config:
        """
        Pydantic configuration
        Tells Pydantic to load from .env file
        """
        env_file = ".env"  # Load from .env file
        case_sensitive = True  # Variable names are case-sensitive


# ============================================
# CREATE SETTINGS INSTANCE
# ============================================
# This creates a single instance that's imported everywhere
# Settings are loaded once when the application starts
settings = Settings()

# ============================================
# USAGE EXAMPLE:
# ============================================
# from app.core.config import settings
# 
# print(settings.DATABASE_URL)
# print(settings.SECRET_KEY)
# ============================================
