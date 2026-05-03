"""
webapp/routes.py
================
将所有平台 API 路由注册到 Tornado Application。
在 make_app() / server_platform.py 里调用一次即可。
"""
from __future__ import annotations

from webapp.handlers import (
    BatchDeleteHandler,
    BatchDownloadHandler,
    BatchMoveHandler,
    FileDownloadHandler,
    FileHandler,
    FilesHandler,
    FileTranscriptHandler,
    FolderHandler,
    FoldersHandler,
    SearchHandler,
    TaskHandler,
    TasksHandler,
    TrashDeleteHandler,
    TrashHandler,
    TrashRestoreHandler,
    UploadHandler,
)

PLATFORM_ROUTES = [
    # Tasks
    (r"/api/platform/tasks", TasksHandler),
    (r"/api/platform/tasks/([^/]+)", TaskHandler),
    # Files
    (r"/api/platform/files", FilesHandler),
    (r"/api/platform/files/([^/]+)/download", FileDownloadHandler),
    (r"/api/platform/files/([^/]+)/transcript", FileTranscriptHandler),
    (r"/api/platform/files/([^/]+)", FileHandler),
    # Upload
    (r"/api/platform/upload", UploadHandler),
    # Folders
    (r"/api/platform/folders", FoldersHandler),
    (r"/api/platform/folders/([^/]+)", FolderHandler),
    # Search
    (r"/api/platform/search", SearchHandler),
    # Trash
    (r"/api/platform/trash", TrashHandler),
    (r"/api/platform/trash/([^/]+)/restore", TrashRestoreHandler),
    (r"/api/platform/trash/([^/]+)", TrashDeleteHandler),
    # Batch
    (r"/api/platform/batch/move", BatchMoveHandler),
    (r"/api/platform/batch/delete", BatchDeleteHandler),
    (r"/api/platform/batch/download", BatchDownloadHandler),
]


def register_platform_routes(app) -> None:
    """将平台路由追加到已有 Tornado app。"""
    app.add_handlers(r".*$", PLATFORM_ROUTES)
