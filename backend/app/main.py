import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router


logging.basicConfig(level=logging.WARNING)
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("app").setLevel(logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title="Task Manager 42", version="0.1.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.oauth_session_secret.get_secret_value(),
    session_cookie="task_manager_oauth",
    max_age=600,
    path="/api/auth/oauth/google",
    same_site="lax",
    https_only=True,
)
app.include_router(auth_router)
app.include_router(users_router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    _request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    error = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": error},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request,
    _exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"success": False, "error": "Invalid request"},
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error(
        "unexpected_request_error exception=%s method=%s path=%s",
        type(exc).__name__,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"},
    )
