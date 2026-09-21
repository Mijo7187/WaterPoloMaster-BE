from typing import Any, Optional, Generic, TypeVar
from pydantic import BaseModel

# Definišemo TypeVar koji predstavlja "bilo koji tip" koji ćemo kasnije proslediti
T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    """
    Standard response wrapper. 
    Generic[T] omogućava da 'data' polje bude bilo koji Pydantic model.
    """
    status: int
    messages: list[str] = []
    data: Optional[T] = None  # Ovde upada tvoja konkretna šema
    detail: Optional[str] = None

# Tvoja success_response funkcija ostaje ista, jer ona samo pravi dict
def success_response(
    data: Any = None,
    messages: list[str] | None = None,
    status_code: int = 200,
) -> dict:
    return {
        "status": status_code,
        "messages": messages or [],
        "data": data,
        "detail": None,
    }

def error_response(
    status_code: int = 400,
    messages: list[str] | None = None,
    detail: str | None = None,
    errors: list[dict] | None = None,
) -> dict:
    """
    Build an error response dict.
    Typically you won't call this directly — the exception handlers do it for you.

    Args:
        status_code: HTTP status code
        messages: List of user-friendly error messages (translatable on BE)
        detail: Technical debug info (hidden in production)
        errors: 422 only — field-level [{loc, msg}], loc without the "body" prefix
    """
    from app.core.config import settings

    response = {
        "status": status_code,
        "messages": messages or [],
        "data": None,
        "detail": detail if settings.APP_ENV != "production" else None,
    }
    if errors is not None:
        response["errors"] = errors
    return response
