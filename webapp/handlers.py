"""
webapp/handlers.py
==================
所有平台 API 的 Tornado RequestHandler。
路由注册见 routes.py。

Phase 1 实现：
  Tasks   GET/POST  /api/platform/tasks
          GET/DELETE /api/platform/tasks/<id>
  Files   GET       /api/platform/files
          GET/PUT/DELETE /api/platform/files/<id>
          GET       /api/platform/files/<id>/download
          GET       /api/platform/files/<id>/transcript

Phase 2 实现：
  Upload  POST      /api/platform/upload
  Folders GET/POST  /api/platform/folders
          PUT/DELETE /api/platform/folders/<id>
  Search  GET       /api/platform/search
  Trash   GET       /api/platform/trash
          POST      /api/platform/trash/<id>/restore
          DELETE    /api/platform/trash/<id>
  Batch   POST      /api/platform/batch/move
          POST      /api/platform/batch/delete
          GET       /api/platform/batch/download
"""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import urllib.parse
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from tornado.web import HTTPError, RequestHandler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import webapp.db as db
from webapp.task_runner import enqueue


# ── 基类 ──────────────────────────────────────────────────────────────────────

class PlatformHandler(RequestHandler):
    def set_default_headers(self) -> None:
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

    def ok(self, data: Any = None, **kwargs) -> None:
        payload = {"ok": True, **({"data": data} if data is not None else {}), **kwargs}
        self.finish(json.dumps(payload, ensure_ascii=False, default=str))

    def err(self, status: int, message: str) -> None:
        self.set_status(status)
        self.finish(json.dumps({"ok": False, "error": message}, ensure_ascii=False))

    def body(self) -> dict:
        try:
            raw = self.request.body.decode("utf-8") or "{}"
            return json.loads(raw)
        except Exception:
            raise HTTPError(400, reason="Invalid JSON body")

    def write_error(self, status_code: int, **kwargs) -> None:
        reason = self._reason or f"HTTP {status_code}"
        exc_info = kwargs.get("exc_info")
        if exc_info:
            exc = exc_info[1]
            if isinstance(exc, HTTPError) and exc.reason:
                reason = exc.reason
            elif isinstance(exc, Exception) and str(exc):
                reason = str(exc)
        if not self._finished:
            self.set_header("Content-Type", "application/json; charset=utf-8")
            self.finish(json.dumps({"ok": False, "error": reason, "status": status_code}, ensure_ascii=False))


# ── Tasks ─────────────────────────────────────────────────────────────────────

class TasksHandler(PlatformHandler):
    """GET /api/platform/tasks           — 任务列表
       POST /api/platform/tasks          — 创建任务
       DELETE /api/platform/tasks?status=completed — 清空已完成任务"""

    def get(self) -> None:
        limit = int(self.get_query_argument("limit", "50"))
        offset = int(self.get_query_argument("offset", "0"))
        tasks = db.list_tasks(limit=limit, offset=offset)
        self.ok(tasks, total=len(tasks))

    def post(self) -> None:
        data = self.body()

        # Legacy modal import: create a pre-completed task record without queuing
        if data.get("_import"):
            if not data.get("topic"):
                raise HTTPError(400, reason="topic 为必填")
            task = db.create_task(data)
            db.update_task_status(
                task["task_id"], "completed",
                file_id=data.get("file_id") or None,
            )
            self.set_status(201)
            self.ok(db.get_task(task["task_id"]))
            return

        # 基础校验
        if not data.get("topic") and not data.get("input_text"):
            raise HTTPError(400, reason="topic 或 input_text 为必填")
        mode = data.get("generation_mode", "llm")
        if mode not in ("llm", "direct"):
            raise HTTPError(400, reason="generation_mode 须为 llm 或 direct")
        if mode == "direct" and not data.get("input_text"):
            raise HTTPError(400, reason="直接输入模式需提供 input_text")

        # 并发限制
        if db.count_active_tasks() >= 3:
            raise HTTPError(429, reason="当前进行中任务已达上限（3个），请稍后再试")

        task = db.create_task(data)
        enqueue(task["task_id"])
        self.set_status(201)
        self.ok(task)

    def delete(self) -> None:
        status = self.get_query_argument("status", "")
        if status != "completed":
            raise HTTPError(400, reason="仅支持 status=completed")
        count = db.delete_completed_tasks()
        self.ok({"deleted": count})


class TaskHandler(PlatformHandler):
    """GET/POST/DELETE /api/platform/tasks/<task_id>"""

    def get(self, task_id: str) -> None:
        task = db.get_task(task_id)
        if not task:
            raise HTTPError(404, reason="任务不存在")
        self.ok(task)

    def post(self, task_id: str) -> None:
        """重试失败任务：POST /api/platform/tasks/<id>  body: {"action":"retry"}"""
        data = self.body()
        if data.get("action") != "retry":
            raise HTTPError(400, reason="未知操作，仅支持 action=retry")
        task = db.get_task(task_id)
        if not task:
            raise HTTPError(404, reason="任务不存在")
        if task["status"] != "failed":
            raise HTTPError(400, reason="只有失败的任务才能重试")
        if db.count_active_tasks() >= 3:
            raise HTTPError(429, reason="当前进行中任务已达上限（3个）")
        updated = db.retry_task(task_id)
        if updated:
            enqueue(task_id)
        self.ok(updated)

    def delete(self, task_id: str) -> None:
        task = db.get_task(task_id)
        if not task:
            raise HTTPError(404, reason="任务不存在")
        # 进行中的任务只能标记失败，不能从队列移除（简化处理）
        if task["status"] in ("generating_text", "synthesizing"):
            db.update_task_status(task_id, "failed", error_msg="用户取消")
        else:
            db.delete_task(task_id)
        self.ok({"task_id": task_id, "deleted": True})


# ── Files ─────────────────────────────────────────────────────────────────────

class FilesHandler(PlatformHandler):
    """GET  /api/platform/files — 文件列表（含搜索/筛选）
       POST /api/platform/files — 注册已有音频文件（旧 demo 生成后调用）"""

    def get(self) -> None:
        folder_id = self.get_query_argument("folder_id", "_unset_")
        if folder_id == "null":
            folder_id = None  # type: ignore[assignment]
        elif folder_id == "_unset_":
            pass  # 不按文件夹过滤
        search = self.get_query_argument("search", "")
        language = self.get_query_argument("language", "")
        scene = self.get_query_argument("scene", "")
        source = self.get_query_argument("source", "")
        limit = int(self.get_query_argument("limit", "50"))
        offset = int(self.get_query_argument("offset", "0"))

        files = db.list_audio_files(
            folder_id=folder_id,
            search=search,
            language=language,
            scene=scene,
            source=source,
            limit=limit,
            offset=offset,
        )
        total = db.count_audio_files()
        self.ok(files, total=total)

    def post(self) -> None:
        """注册旧 demo 生成的音频文件到平台 DB（file_path 必须已存在于磁盘）。"""
        data = self.body()
        file_path_str = data.get("file_path", "")
        if not file_path_str:
            raise HTTPError(400, reason="file_path 不能为空")
        fpath = Path(file_path_str)
        if not fpath.exists():
            raise HTTPError(400, reason=f"文件不存在: {file_path_str}")
        file_size = fpath.stat().st_size
        duration = float(data.get("duration") or 0)
        if duration == 0:
            try:
                from pydub import AudioSegment as _AS
                _seg = _AS.from_file(str(fpath))
                duration = len(_seg) / 1000.0
                del _seg
            except Exception:
                pass
        ext = fpath.suffix.lstrip(".").lower() or "mp3"
        folder_id = data.get("folder_id") or None
        record = db.create_audio_file({
            "file_name": data.get("file_name") or fpath.name,
            "file_path": str(fpath.resolve()),
            "source": "generated",
            "duration": duration,
            "format": data.get("format") or ext,
            "file_size": file_size,
            "language": data.get("language") or "",
            "speaker_count": int(data.get("speaker_count") or 0) or None,
            "scene": data.get("scene") or "other",
            "topic": data.get("topic") or "",
            "folder_id": folder_id,
        })
        self.set_status(201)
        self.ok(record)


class FileHandler(PlatformHandler):
    """GET/PUT/DELETE /api/platform/files/<file_id>"""

    def get(self, file_id: str) -> None:
        f = db.get_audio_file(file_id)
        if not f:
            raise HTTPError(404, reason="文件不存在")
        self.ok(f)

    def put(self, file_id: str) -> None:
        """更新文件元数据（文件名/场景/语言/标签/文件夹）"""
        f = db.get_audio_file(file_id)
        if not f:
            raise HTTPError(404, reason="文件不存在")
        data = self.body()
        allowed = {"file_name", "scene", "language", "speaker_count", "topic", "folder_id"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if "tags" in data:
            updates["tags"] = json.dumps(data["tags"], ensure_ascii=False)
        if updates:
            db.update_audio_file(file_id, **updates)
        self.ok(db.get_audio_file(file_id))

    def delete(self, file_id: str) -> None:
        """软删除（移入回收站）"""
        f = db.get_audio_file(file_id)
        if not f:
            raise HTTPError(404, reason="文件不存在")
        db.soft_delete_file(file_id)
        self.ok({"file_id": file_id, "deleted": True})


class FileDownloadHandler(PlatformHandler):
    """GET /api/platform/files/<file_id>/download"""

    def get(self, file_id: str) -> None:
        f = db.get_audio_file(file_id)
        if not f:
            raise HTTPError(404, reason="文件不存在")
        fpath = Path(f["file_path"])
        if not fpath.exists():
            raise HTTPError(404, reason="音频文件已丢失，请重新生成")
        content_type, _ = mimetypes.guess_type(fpath.name)
        safe_name = urllib.parse.quote(fpath.name)
        self.set_header("Content-Type", content_type or "application/octet-stream")
        self.set_header(
            "Content-Disposition",
            f"attachment; filename*=UTF-8''{safe_name}",
        )
        self.set_header("Content-Length", str(fpath.stat().st_size))
        with open(fpath, "rb") as fp:
            self.finish(fp.read())


class FileTranscriptHandler(PlatformHandler):
    """GET /api/platform/files/<file_id>/transcript?type=json|srt"""

    def get(self, file_id: str) -> None:
        f = db.get_audio_file(file_id)
        if not f:
            raise HTTPError(404, reason="文件不存在")
        t = self.get_query_argument("type", "json")
        if t == "srt":
            content = f.get("transcript_srt") or ""
            fname = f["file_name"].rsplit(".", 1)[0] + "_transcript.srt"
            self.set_header("Content-Type", "text/plain; charset=utf-8")
            self.set_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(fname)}")
            self.finish(content)
        else:
            content = f.get("transcript_json") or "[]"
            fname = f["file_name"].rsplit(".", 1)[0] + "_transcript.json"
            self.set_header("Content-Type", "application/json; charset=utf-8")
            self.set_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(fname)}")
            self.finish(content)


# ── Upload ────────────────────────────────────────────────────────────────────

class UploadHandler(PlatformHandler):
    """POST /api/platform/upload — 上传音频文件（multipart/form-data）"""

    async def post(self) -> None:
        allowed_exts = {".wav", ".mp3", ".m4a", ".mp4"}
        max_size = 500 * 1024 * 1024  # 500 MB

        if not self.request.files.get("file"):
            raise HTTPError(400, reason="缺少 file 字段")

        upload = self.request.files["file"][0]
        original_name: str = upload["filename"]
        ext = Path(original_name).suffix.lower()
        if ext not in allowed_exts:
            raise HTTPError(400, reason=f"不支持的格式 {ext}，仅支持 WAV/MP3/M4A/MP4")
        if len(upload["body"]) > max_size:
            raise HTTPError(400, reason="文件超过 500MB 限制")

        import time, hashlib
        ts = int(time.time())
        slug = hashlib.md5(original_name.encode()).hexdigest()[:8]
        save_name = f"{Path(original_name).stem}_{ts}_{slug}{ext}"

        dest_dir = ROOT / "storage" / "uploaded"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / save_name
        dest.write_bytes(upload["body"])

        language = self.get_body_argument("language", "中文")
        scene = self.get_body_argument("scene", "other")
        speaker_count = int(self.get_body_argument("speaker_count", "1"))
        topic = self.get_body_argument("topic", Path(original_name).stem)
        folder_id = self.get_body_argument("folder_id", None) or None

        # 尝试读取音频时长
        duration = 0.0
        try:
            from pydub import AudioSegment
            seg = AudioSegment.from_file(str(dest))
            duration = len(seg) / 1000.0
        except Exception:
            pass

        file_record = db.create_audio_file({
            "file_name": save_name,
            "file_path": str(dest),
            "source": "uploaded",
            "duration": duration,
            "format": ext.lstrip("."),
            "file_size": len(upload["body"]),
            "language": language,
            "speaker_count": speaker_count,
            "scene": scene,
            "topic": topic,
            "folder_id": folder_id,
        })
        self.set_status(201)
        self.ok(file_record)


# ── Folders ───────────────────────────────────────────────────────────────────

class FoldersHandler(PlatformHandler):
    """GET /api/platform/folders — 文件夹树（全量）
       POST /api/platform/folders — 新建文件夹"""

    def get(self) -> None:
        all_folders = db.list_folders(_all=True)
        # 构建树形结构
        folder_map = {f["folder_id"]: {**f, "children": []} for f in all_folders}
        roots = []
        for f in folder_map.values():
            pid = f.get("parent_id")
            if pid and pid in folder_map:
                folder_map[pid]["children"].append(f)
            else:
                roots.append(f)
        self.ok(roots)

    def post(self) -> None:
        data = self.body()
        name = (data.get("name") or "").strip()
        if not name:
            raise HTTPError(400, reason="文件夹名不能为空")
        parent_id = data.get("parent_id") or None

        # 最多3层嵌套
        if parent_id:
            depth = 1
            cur = db.get_folder(parent_id)
            while cur and cur.get("parent_id"):
                depth += 1
                cur = db.get_folder(cur["parent_id"])
            if depth >= 3:
                raise HTTPError(400, reason="文件夹最多嵌套 3 层")

        folder = db.create_folder(name, parent_id)
        self.set_status(201)
        self.ok(folder)


class FolderHandler(PlatformHandler):
    """PUT/DELETE /api/platform/folders/<folder_id>"""

    def put(self, folder_id: str) -> None:
        if not db.get_folder(folder_id):
            raise HTTPError(404, reason="文件夹不存在")
        data = self.body()
        name = (data.get("name") or "").strip()
        if not name:
            raise HTTPError(400, reason="文件夹名不能为空")
        db.rename_folder(folder_id, name)
        self.ok(db.get_folder(folder_id))

    def delete(self, folder_id: str) -> None:
        if not db.get_folder(folder_id):
            raise HTTPError(404, reason="文件夹不存在")
        db.delete_folder(folder_id)
        self.ok({"folder_id": folder_id, "deleted": True})


# ── Search ────────────────────────────────────────────────────────────────────

class SearchHandler(PlatformHandler):
    """GET /api/platform/search — 全局搜索"""

    def get(self) -> None:
        search = self.get_query_argument("q", "")
        language = self.get_query_argument("language", "")
        scene = self.get_query_argument("scene", "")
        source = self.get_query_argument("source", "")
        limit = int(self.get_query_argument("limit", "50"))
        offset = int(self.get_query_argument("offset", "0"))

        files = db.list_audio_files(
            search=search,
            language=language,
            scene=scene,
            source=source,
            limit=limit,
            offset=offset,
        )
        self.ok(files, total=len(files))


# ── Trash ─────────────────────────────────────────────────────────────────────

class TrashHandler(PlatformHandler):
    """GET /api/platform/trash — 回收站列表"""

    def get(self) -> None:
        limit = int(self.get_query_argument("limit", "50"))
        offset = int(self.get_query_argument("offset", "0"))
        files = db.list_audio_files(include_deleted=True, limit=limit, offset=offset)
        self.ok(files, total=len(files))


class TrashRestoreHandler(PlatformHandler):
    """POST /api/platform/trash/<file_id>/restore"""

    def post(self, file_id: str) -> None:
        f = db.get_audio_file(file_id)
        if not f:
            raise HTTPError(404, reason="文件不存在")
        db.restore_file(file_id)
        self.ok({"file_id": file_id, "restored": True})


class TrashDeleteHandler(PlatformHandler):
    """DELETE /api/platform/trash/<file_id> — 永久删除"""

    def delete(self, file_id: str) -> None:
        f = db.get_audio_file(file_id)
        if not f:
            raise HTTPError(404, reason="文件不存在")
        # 同时删除实体文件
        fpath = Path(f["file_path"])
        if fpath.exists():
            try:
                fpath.unlink()
            except Exception:
                pass
        db.hard_delete_file(file_id)
        self.ok({"file_id": file_id, "permanently_deleted": True})


# ── Batch ─────────────────────────────────────────────────────────────────────

class BatchMoveHandler(PlatformHandler):
    """POST /api/platform/batch/move"""

    def post(self) -> None:
        data = self.body()
        file_ids: list[str] = data.get("file_ids", [])
        folder_id: str | None = data.get("folder_id")  # None = 移到根目录
        if not file_ids:
            raise HTTPError(400, reason="file_ids 不能为空")
        if len(file_ids) > 50:
            raise HTTPError(400, reason="单次批量操作最多 50 个文件")
        for fid in file_ids:
            db.move_file(fid, folder_id)
        self.ok({"moved": len(file_ids), "folder_id": folder_id})


class BatchDeleteHandler(PlatformHandler):
    """POST /api/platform/batch/delete"""

    def post(self) -> None:
        data = self.body()
        file_ids: list[str] = data.get("file_ids", [])
        if not file_ids:
            raise HTTPError(400, reason="file_ids 不能为空")
        if len(file_ids) > 50:
            raise HTTPError(400, reason="单次批量操作最多 50 个文件")
        for fid in file_ids:
            db.soft_delete_file(fid)
        self.ok({"deleted": len(file_ids)})


class BatchDownloadHandler(PlatformHandler):
    """GET /api/platform/batch/download?ids=id1,id2,..."""

    def get(self) -> None:
        ids_param = self.get_query_argument("ids", "")
        file_ids = [i.strip() for i in ids_param.split(",") if i.strip()]
        if not file_ids:
            raise HTTPError(400, reason="ids 参数不能为空")
        if len(file_ids) > 50:
            raise HTTPError(400, reason="批量下载最多 50 个文件")

        buf = BytesIO()
        total_size = 0
        size_limit = 2 * 1024 * 1024 * 1024  # 2 GB

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fid in file_ids:
                f = db.get_audio_file(fid)
                if not f:
                    continue
                fpath = Path(f["file_path"])
                if not fpath.exists():
                    continue
                fsize = fpath.stat().st_size
                if total_size + fsize > size_limit:
                    break
                total_size += fsize
                zf.write(fpath, f["file_name"])

        buf.seek(0)
        self.set_header("Content-Type", "application/zip")
        self.set_header("Content-Disposition", "attachment; filename=corpus_export.zip")
        self.set_header("Content-Length", str(len(buf.getvalue())))
        self.finish(buf.getvalue())


# ── Stats ─────────────────────────────────────────────────────────────────────

class StatsHandler(PlatformHandler):
    """GET /api/platform/stats — 平台统计摘要"""

    def get(self) -> None:
        with db._conn() as c:
            total = c.execute(
                "SELECT COUNT(*) FROM audio_files WHERE deleted=0"
            ).fetchone()[0]
            total_dur = c.execute(
                "SELECT COALESCE(SUM(duration),0) FROM audio_files WHERE deleted=0"
            ).fetchone()[0]
            active_tasks = c.execute(
                "SELECT COUNT(*) FROM tasks WHERE status IN ('queued','generating_text','synthesizing')"
            ).fetchone()[0]
            trash_count = c.execute(
                "SELECT COUNT(*) FROM audio_files WHERE deleted=1"
            ).fetchone()[0]
            by_lang = c.execute(
                "SELECT language, COUNT(*) AS cnt FROM audio_files WHERE deleted=0 "
                "GROUP BY language ORDER BY cnt DESC LIMIT 5"
            ).fetchall()
            by_scene = c.execute(
                "SELECT scene, COUNT(*) AS cnt FROM audio_files WHERE deleted=0 "
                "GROUP BY scene ORDER BY cnt DESC"
            ).fetchall()
            total_size = c.execute(
                "SELECT COALESCE(SUM(file_size),0) FROM audio_files WHERE deleted=0"
            ).fetchone()[0]
        self.ok({
            "total_files": int(total),
            "total_duration": float(total_dur),
            "total_size": int(total_size),
            "active_tasks": int(active_tasks),
            "trash_count": int(trash_count),
            "by_language": [dict(r) for r in by_lang],
            "by_scene": [dict(r) for r in by_scene],
        })


# ── Legacy Demo Page ──────────────────────────────────────────────────────────

class LegacyPageHandler(RequestHandler):
    """GET /legacy — 原 Demo 页面"""

    def get(self) -> None:
        legacy_html = ROOT / "static" / "legacy.html"
        if not legacy_html.exists():
            self.set_status(404)
            self.finish("Legacy demo not found")
            return
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.finish(legacy_html.read_bytes())
