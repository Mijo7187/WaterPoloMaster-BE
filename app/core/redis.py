# ============================================
# REDIS - Redis Client Configuration
# ============================================
# This file creates and manages the Redis connection
# Used for storing auth tokens (access + refresh)
#
# Redis Key Structure:
#   access:{user_id}  → access token  (TTL = ACCESS_TOKEN_EXPIRE_MINUTES)
#   refresh:{user_id} → refresh token (TTL = REFRESH_TOKEN_EXPIRE_DAYS)
# ============================================

import redis

from app.core.config import settings


# ============================================
# REDIS CLIENT
# ============================================
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    decode_responses=True,  # Return strings instead of bytes
)


def store_access_token(user_id: int, token: str) -> None:
    """Store access token in Redis with TTL matching token expiration"""
    key = f"access:{user_id}"
    redis_client.setex(key, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, token)


def get_access_token(user_id: int) -> str | None:
    """Get access token from Redis"""
    key = f"access:{user_id}"
    return redis_client.get(key)


def store_refresh_token(user_id: int, token: str) -> None:
    """Store refresh token in Redis with TTL matching token expiration"""
    key = f"refresh:{user_id}"
    redis_client.setex(key, settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, token)


def get_refresh_token(user_id: int) -> str | None:
    """Get refresh token from Redis"""
    key = f"refresh:{user_id}"
    return redis_client.get(key)


def delete_user_tokens(user_id: int) -> None:
    """Delete both access and refresh tokens for a user (logout)"""
    redis_client.delete(f"access:{user_id}", f"refresh:{user_id}")
