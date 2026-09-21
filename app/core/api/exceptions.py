# ============================================
# CUSTOM EXCEPTIONS
# ============================================
# Custom exception classes for the entire app.
# Throw these from services/dependencies instead of HTTPException.
#
# WHY:
# - Keeps business logic clean (no HTTP details in services)
# - All exceptions funnel through global handlers
# - Every error response has the same JSON shape
# ============================================


class AppException(Exception):
    """
    Base exception for all application errors.
    
    Every custom exception inherits from this.
    The global handler catches this and returns a standardized JSON response.
    
    Args:
        status_code: HTTP status code
        message: Single error message (backward-compatible)
        errors: List of error strings when there are MULTIPLE problems
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        errors: list[str] | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.message = message
        # If errors list not provided, wrap the single message into a list
        self.errors = errors if errors is not None else [message]
        # Optional HTTP headers to attach to the response (e.g. Retry-After)
        self.headers = headers
        super().__init__(message)


class NotFoundException(AppException):
    """Resource not found (404)"""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(status_code=404, message=message)


class BadRequestException(AppException):
    """Bad request / validation error (400)"""

    def __init__(self, message: str = "Bad request", errors: list[str] | None = None):
        super().__init__(status_code=400, message=message, errors=errors)


class UnauthorizedException(AppException):
    """Authentication required or failed (401)"""

    def __init__(self, message: str = "Not authenticated"):
        super().__init__(status_code=401, message=message)


class ForbiddenException(AppException):
    """Insufficient permissions (403)"""

    def __init__(self, message: str = "Access forbidden"):
        super().__init__(status_code=403, message=message)


class TooManyRequestsException(AppException):
    """
    Client sent too many requests (429).

    Raised by the rate limiter and the duplicate-request guard.
    `retry_after` is echoed back in the standard Retry-After header so a
    well-behaved client knows how long to wait before trying again.
    """

    def __init__(
        self,
        message: str = "Too many requests",
        retry_after: int | None = None,
    ):
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(status_code=429, message=message, headers=headers)


class ConflictException(AppException):
    """Resource conflict, e.g. duplicate email (409)"""

    def __init__(self, message: str = "Resource conflict", errors: list[str] | None = None):
        super().__init__(status_code=409, message=message, errors=errors)


class ValidationException(AppException):
    """
    Business-rule validation error (422) with field-level locations.

    Same response shape as a Pydantic 422 — `messages` as "loc -> path: msg"
    strings, plus `errors: [{loc, msg}]` so the frontend can pin each error on
    a field or a list row, e.g. loc=["installments_list", 1, "period_end"].

    Raise it with one error: ValidationException(["amount"], "must equal ...")
    or several: ValidationException(errors=[(loc, msg), ...]).
    """

    def __init__(
        self,
        loc: list | None = None,
        msg: str | None = None,
        errors: list[tuple[list, str]] | None = None,
    ):
        pairs = list(errors or [])
        if loc is not None:
            pairs.insert(0, (loc, msg or "Invalid value"))
        self.field_errors = [{"loc": list(l), "msg": m} for l, m in pairs]
        messages = [
            f"{' -> '.join(str(p) for p in e['loc'])}: {e['msg']}"
            for e in self.field_errors
        ]
        super().__init__(
            status_code=422,
            message=messages[0] if messages else "Validation error",
            errors=messages or ["Validation error"],
        )
