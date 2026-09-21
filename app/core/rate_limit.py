# ============================================
# RATE LIMIT - Brute-force / request-flood protection
# ============================================
# Fixed-window counters used to throttle abusive traffic.
#
# WHY:
# Auth endpoints are the most attacked part of any API. Without a limit,
# anyone (a bot scanning the internet, or a buggy frontend retry loop)
# can hammer /auth/login thousands of times per minute.
#
# HOW IT WORKS:
#   Every "hit" increments a counter in Redis under a key that encodes
#   scope + identity (IP or email) + the current time window.
#   The key expires automatically when the window ends, so there is
#   nothing to clean up.
#
#   key: rl:{scope}:{identity}:{window_index}  → int, TTL = window_seconds
#
# REDIS DOWN?
#   Falls back to an in-process dict so the API still throttles
#   (per worker process) instead of failing open completely.
#
# USAGE (router):
#   @router.post("/login", dependencies=[Depends(rate_limit("login", 10, 60))])
#
# USAGE (service / manual):
#   allowed, retry_after = hit("login:email", email, 5, 900)
# ============================================

import time
import hashlib
import logging
from typing import Callable, Tuple

from fastapi import Request

from app.core.config import settings
from app.core.api.exceptions import TooManyRequestsException
from app.core.redis import redis_client


logger = logging.getLogger("app.security")


# ============================================
# IN-MEMORY FALLBACK (used only if Redis is unreachable)
# ============================================
# Maps full redis key -> (count, window_expires_at_epoch)
_local_counters: dict[str, tuple[int, float]] = {}


def _local_hit(key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
    """Fixed-window counter kept in this process. Fallback only."""
    now = time.time()

    # Opportunistic cleanup so the dict cannot grow forever
    if len(_local_counters) > 10_000:
        for k, (_, exp) in list(_local_counters.items()):
            if exp <= now:
                _local_counters.pop(k, None)

    count, expires_at = _local_counters.get(key, (0, 0.0))
    if expires_at <= now:
        count, expires_at = 0, now + window_seconds

    count += 1
    _local_counters[key] = (count, expires_at)

    if count > limit:
        return False, max(1, int(expires_at - now))
    return True, 0


# ============================================
# CORE COUNTER
# ============================================
def hit(scope: str, identity: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
    """
    Register one request against a counter.

    Args:
        scope: What is being limited, e.g. "login", "login:email", "refresh"
        identity: Who is being limited, e.g. an IP or an email
        limit: Max allowed hits inside the window
        window_seconds: Window length in seconds

    Returns:
        (allowed, retry_after_seconds) — retry_after is 0 when allowed
    """
    if not settings.RATE_LIMIT_ENABLED:
        return True, 0

    window_index = int(time.time() // window_seconds)
    key = f"rl:{scope}:{identity}:{window_index}"

    try:
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        count, _ = pipe.execute()
    except Exception as exc:  # Redis unreachable / misconfigured
        logger.warning("Rate limit falling back to in-memory store: %s", exc)
        return _local_hit(key, limit, window_seconds)

    if count > limit:
        # Time left until this window rolls over
        retry_after = window_seconds - int(time.time() % window_seconds)
        return False, max(1, retry_after)

    return True, 0


def peek(scope: str, identity: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
    """
    Read a counter WITHOUT incrementing it.

    Used by the failed-login lockout: every attempt must be checked, but only
    a genuinely failed attempt should count against the user. Incrementing
    here would lock people out on correct passwords too.

    Returns:
        (allowed, retry_after_seconds)
    """
    if not settings.RATE_LIMIT_ENABLED:
        return True, 0

    window_index = int(time.time() // window_seconds)
    key = f"rl:{scope}:{identity}:{window_index}"

    try:
        raw = redis_client.get(key)
        count = int(raw) if raw else 0
    except Exception:
        count, expires_at = _local_counters.get(key, (0, 0.0))
        if expires_at <= time.time():
            count = 0

    if count >= limit:
        retry_after = window_seconds - int(time.time() % window_seconds)
        return False, max(1, retry_after)

    return True, 0


def reset(scope: str, identity: str, window_seconds: int) -> None:
    """
    Clear the current window for an identity.

    Called after a SUCCESSFUL login so a user who mistyped their password
    a few times is not still counted against the lockout.
    """
    window_index = int(time.time() // window_seconds)
    key = f"rl:{scope}:{identity}:{window_index}"
    try:
        redis_client.delete(key)
    except Exception:
        _local_counters.pop(key, None)


# ============================================
# DUPLICATE REQUEST GUARD
# ============================================
def reject_duplicate(scope: str, identity: str, window_seconds: int) -> None:
    """
    Reject the SAME request repeated within `window_seconds`.

    This is different from the rate limiter above. The limiter allows N
    *different* requests per minute; this allows exactly ONE identical
    request per short window. It is what stops a frontend retry loop
    (or a double-clicked login button) from replaying the same credentials
    dozens of times per second.

    Implemented as a Redis SET NX lock: the first caller sets the key and
    passes, everyone else finds it already there and is turned away until
    it expires.

    Args:
        scope: Bucket label, e.g. "dup:login"
        identity: Stable fingerprint of the request (see _fingerprint)
        window_seconds: How long an identical request stays blocked

    Raises:
        TooManyRequestsException (429) if this is a duplicate.
    """
    if not settings.RATE_LIMIT_ENABLED or window_seconds <= 0:
        return

    key = f"dup:{scope}:{identity}"

    try:
        # nx=True → only sets if the key does NOT exist
        acquired = redis_client.set(key, "1", ex=window_seconds, nx=True)
    except Exception as exc:
        logger.warning("Duplicate guard falling back to in-memory store: %s", exc)
        # One hit per window == the same lock, expressed with the local counter
        allowed, _ = _local_hit(key, 1, window_seconds)
        acquired = allowed

    if not acquired:
        logger.warning("Duplicate request blocked: scope=%s id=%s", scope, identity)
        raise TooManyRequestsException(
            "Duplicate request. Please wait before retrying.",
            retry_after=window_seconds,
        )


def fingerprint(*parts: str) -> str:
    """
    Build a short, non-reversible id for a request.

    Hashed because the parts can include secrets (a refresh token) or
    personal data (an email) and these end up in Redis keys and logs.
    """
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ============================================
# CLIENT IP RESOLUTION
# ============================================
def get_client_ip(request: Request) -> str:
    """
    Best-effort client IP.

    Behind a reverse proxy (nginx, Render, Railway, Fly...) the socket peer is
    the proxy, so the real client sits in X-Forwarded-For. That header is
    trivially spoofable when the app is exposed directly, so we only read it
    when TRUST_PROXY_HEADERS is switched on for the deployment.
    """
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Left-most entry is the original client
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

    return request.client.host if request.client else "unknown"


# ============================================
# FASTAPI DEPENDENCY FACTORY
# ============================================
def rate_limit(scope: str, limit: int, window_seconds: int) -> Callable:
    """
    Build a FastAPI dependency that throttles a route by client IP.

    Args:
        scope: Label for this bucket — keep it unique per endpoint group
        limit: Max requests per window from one IP
        window_seconds: Window length in seconds

    Returns:
        An async dependency. Raises TooManyRequestsException (429) when over.

    Example:
        @router.post("/login", dependencies=[Depends(rate_limit("login", 10, 60))])
    """

    async def dependency(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        ip = get_client_ip(request)
        allowed, retry_after = hit(scope, ip, limit, window_seconds)

        if not allowed:
            logger.warning(
                "Rate limit hit: scope=%s ip=%s path=%s ua=%s",
                scope,
                ip,
                request.url.path,
                request.headers.get("user-agent", "-"),
            )
            raise TooManyRequestsException(
                f"Too many requests. Try again in {retry_after} seconds.",
                retry_after=retry_after,
            )

    return dependency
