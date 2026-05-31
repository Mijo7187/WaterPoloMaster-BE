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

    def __init__(self, status_code: int, message: str, errors: list[str] | None = None):
        self.status_code = status_code
        self.message = message
        # If errors list not provided, wrap the single message into a list
        self.errors = errors if errors is not None else [message]
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


class ConflictException(AppException):
    """Resource conflict, e.g. duplicate email (409)"""

    def __init__(self, message: str = "Resource conflict", errors: list[str] | None = None):
        super().__init__(status_code=409, message=message, errors=errors)
