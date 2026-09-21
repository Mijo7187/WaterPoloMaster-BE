# ============================================
# EXCEPTION HANDLERS - Global Error Handling
# ============================================
# These handlers catch every exception in the app and
# return a uniform JSON response using ApiResponse shape.
#
# Registered in main.py via `register_exception_handlers(app)`.
#
# WHAT GETS CAUGHT:
# 1. AppException (and subclasses) – our custom business errors
# 2. HTTPException – FastAPI's built-in (from dependencies, etc.)
# 3. RequestValidationError – Pydantic validation failures (422)
# 4. Exception – unexpected / unhandled errors (500)
# ============================================

import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.api.exceptions import AppException
from app.core.api.responses import error_response


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI app."""

    # --------------------------------------------------
    # 1. Handle our custom AppException (and subclasses)
    # --------------------------------------------------
    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                status_code=exc.status_code,
                messages=exc.errors,
                detail=f"{type(exc).__name__}: {exc.message}",
                # ValidationException carries field-level locations.
                errors=getattr(exc, "field_errors", None),
            ),
            # Some errors carry headers (e.g. Retry-After on 429)
            headers=getattr(exc, "headers", None),
        )

    # --------------------------------------------------
    # 2. Handle FastAPI's HTTPException
    #    (raised by dependencies like HTTPBearer, etc.)
    # --------------------------------------------------
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                status_code=exc.status_code,
                messages=[str(exc.detail)],
                detail=f"HTTPException({exc.status_code}): {exc.detail}",
            ),
        )

    # --------------------------------------------------
    # 3. Handle Pydantic validation errors (422)
    # --------------------------------------------------
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Collect all validation messages into a readable string
        error_list = []
        field_errors = []
        for err in exc.errors():
            field = " -> ".join(str(loc) for loc in err["loc"])
            error_list.append(f"{field}: {err['msg']}")
            # Same {loc, msg} shape as ValidationException, so the frontend
            # reads row-level errors one way. "body" is dropped from loc.
            loc = list(err["loc"])
            if loc and loc[0] == "body":
                loc = loc[1:]
            field_errors.append({"loc": loc, "msg": err["msg"]})

        return JSONResponse(
            status_code=422,
            content=error_response(
                status_code=422,
                messages=error_list if error_list else ["Validation error"],
                detail=f"RequestValidationError: {len(error_list)} field(s) failed",
                errors=field_errors,
            ),
        )

    # --------------------------------------------------
    # 4. Catch-all for unexpected errors (500)
    # --------------------------------------------------
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        # Log the full traceback on server side
        tb = traceback.format_exc()
        print(f"[UNHANDLED ERROR] {type(exc).__name__}: {exc}\n{tb}")

        return JSONResponse(
            status_code=500,
            content=error_response(
                status_code=500,
                messages=["Internal server error"],
                detail=f"{type(exc).__name__}: {exc}",
            ),
        )
