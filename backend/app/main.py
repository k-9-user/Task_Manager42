import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.projects import router as projects_router
from app.routers.tasks import router as tasks_router
from app.routers.gdpr import router as gdpr_router
from app.routers.notifications import router as notifications_router
from app.routers.attachments import router as attachments_router
from app.routers.export_import import router as export_import_router
from app.routers.public_api import router as public_api_router
from app.routers.search import router as search_router


logger = logging.getLogger(__name__)

app = FastAPI(title="Task Manager 42", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(gdpr_router)
app.include_router(notifications_router)
app.include_router(attachments_router)
app.include_router(export_import_router)
app.include_router(public_api_router)
app.include_router(search_router)


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
        "Unhandled %s during %s %s",
        type(exc).__name__,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"},
    )
