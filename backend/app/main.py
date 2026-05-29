"""FastAPI 应用入口。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.v1 import admin, auth, files, folders, meta, tasks, voices
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.providers.storage.minio_client import ensure_bucket

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} (env={settings.APP_ENV})")
    ensure_bucket()
    # 启动时尝试初始化音色目录（失败只 warning，不阻断启动）
    try:
        from app.scripts.init_voice_catalog import init_voice_catalog_if_empty
        init_voice_catalog_if_empty()
    except Exception as exc:
        logger.warning(f"Voice catalog init skipped (CosyVoice unavailable?): {exc}")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Audio Corpus Platform API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
app.include_router(folders.router, prefix="/api/v1/folders", tags=["folders"])
app.include_router(meta.router, prefix="/api/v1/meta", tags=["meta"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(voices.router, prefix="/api/v1/voices", tags=["voices"])
