import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db import model_imports  # noqa: F401

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_display_name,
    version=settings.app_version,
    description="商脉 BizPulse 本地商业情报与商业验证后端 API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for err in exc.errors():
        clean = {k: v for k, v in err.items() if k not in {"ctx", "url"}}
        ctx = err.get("ctx")
        if isinstance(ctx, dict):
            serializable_ctx = {k: str(v) for k, v in ctx.items() if isinstance(v, (str, int, float, bool))}
            if serializable_ctx:
                clean["ctx"] = serializable_ctx
        errors.append(clean)
    return JSONResponse(
        status_code=422,
        content={"success": False, "data": None, "message": "Validation failed", "errors": errors},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"success": False, "data": None, "message": "Internal server error"},
    )


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_display_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api": settings.api_v1_prefix,
    }


@app.on_event("startup")
async def start_scheduler_hook() -> None:
    from app.services.scheduler import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
async def stop_scheduler_hook() -> None:
    from app.services.scheduler import stop_scheduler
    stop_scheduler()


app.include_router(api_router, prefix=settings.api_v1_prefix)
