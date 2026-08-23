"""FastAPI Application factory with async lifespan, structured JSON error handlers, and static assets."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__, __app_name__
from app.config import settings
from app.core.logger import setup_logging
from app.db.migrations import run_migrations
from app.services.telegram_service import telegram_service
from app.services.download_manager import download_manager

# API Routers
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.telegram import router as telegram_router
from app.api.sources import router as sources_router
from app.api.downloads import router as downloads_router
from app.api.storage import router as storage_router
from app.api.jellyfin import router as jellyfin_router
from app.api.logs import router as logs_router
from app.api.settings import router as settings_router
from app.api.system import router as system_router
from app.api.health import router as health_router

logger = logging.getLogger("TelegramDownloader")
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle hooks for clean startup and shutdown."""
    # 1. Startup
    setup_logging(settings.log_level)
    logger.info(f"Starting {__app_name__} v{__version__}...")
    settings.ensure_directories()

    try:
        run_migrations()
    except Exception as e:
        logger.critical(f"Database migration failed: {e}", exc_info=True)
        raise

    try:
        await telegram_service.initialize()
    except Exception as e:
        logger.error(f"Telegram auto-initialization error: {e}")

    try:
        await download_manager.start()
    except Exception as e:
        logger.error(f"Download manager failed to start: {e}", exc_info=True)

    logger.info(f"{__app_name__} is fully ready. Dashboard running at http://{settings.host}:{settings.port}")

    yield

    # 2. Shutdown
    logger.info(f"Shutting down {__app_name__}...")
    try:
        await download_manager.stop()
    except Exception as e:
        logger.warning(f"Error stopping download manager: {e}")

    try:
        await telegram_service.disconnect()
    except Exception as e:
        logger.warning(f"Error disconnecting Telegram client: {e}")

    logger.info(f"{__app_name__} shutdown complete.")


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance."""
    app = FastAPI(
        title=__app_name__,
        version=__version__,
        description="24/7 Telegram Downloader & Media Sync for Windows 11 Server",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # CORS configuration for LAN and Tailscale access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -------------------------------------------------------------
    # Structured JSON Exception Handlers (Never return raw HTML 500)
    # -------------------------------------------------------------
    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "message": exc.detail,
                "code": exc.status_code,
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            errors.append(f"{loc}: {err.get('msg')}")
        message = "; ".join(errors) if errors else "Invalid request data."
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "status": "error",
                "message": message,
                "code": 422,
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def global_unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled server exception on {request.method} {request.url}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "An internal server error occurred. Please check system logs.",
                "code": 500,
            },
        )

    # -------------------------------------------------------------
    # Register API Routers
    # -------------------------------------------------------------
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(telegram_router)
    app.include_router(sources_router)
    app.include_router(downloads_router)
    app.include_router(storage_router)
    app.include_router(jellyfin_router)
    app.include_router(logs_router)
    app.include_router(settings_router)
    app.include_router(system_router)

    # -------------------------------------------------------------
    # Static Assets & Web Dashboard
    # -------------------------------------------------------------
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    @app.get("/{full_path:path}")
    async def serve_spa_frontend(request: Request, full_path: str = ""):
        # If API path, let it 404 cleanly in JSON
        if full_path.startswith("api/") or full_path.startswith("health") or full_path.startswith("static/"):
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "error", "message": "API endpoint not found.", "code": 404}
            )

        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": f"{__app_name__} API is running. Web UI loading..."}
        )

    return app


app = create_app()
