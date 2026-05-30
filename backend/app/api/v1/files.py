"""文件 API：列表 / 详情 / 下载 / 软删除。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from datetime import datetime as _dt
from pathlib import Path
import shutil
import subprocess
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.models import AudioFile, Folder, Tag, Task, Transcript
from app.providers.storage.minio_client import (
    build_audio_key,
    delete_object,
    get_object_stream,
    get_presigned_download_url,
    upload_file as minio_upload_file,
)
from app.schemas.audio_file import (
    AudioFileDownload,
    AudioFileOut,
    AudioFileUpdate,
    TranscriptLine,
    TranscriptResponse,
)
from app.services.audio import parse_manual_dialogue
from app.services.tags import upsert_tags_by_names

_settings = get_settings()
_ALLOWED_EXT = {".mp3", ".wav", ".m4a", ".mp4"}

router = APIRouter()


@router.get("", response_model=list[AudioFileOut])
def list_files(
    current_user: CurrentUser,
    db: DbSession,
    mine_only: bool = Query(False, description="仅查看自己的文件（我的音频）"),
    folder_id: uuid.UUID | None = Query(None, description="按文件夹过滤"),
    root_only: bool = Query(False, description="仅根目录（无文件夹）"),
    q: str | None = Query(None, description="按文件名/主题模糊搜索"),
    language: str | None = None,
    scene: str | None = None,
    source: str | None = None,
    speaker_count: int | None = Query(None, ge=1, le=10),
    duration_min: int | None = Query(None, ge=0, description="最短时长（秒）"),
    duration_max: int | None = Query(None, ge=0, description="最长时长（秒）"),
    date_from: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
    date_to: str | None = Query(None, description="截止日期 YYYY-MM-DD"),
    tags: list[str] | None = Query(None, description="标签（AND 关系）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[AudioFileOut]:
    """全部文件 / 我的文件 / 高级搜索：filter 组合。"""
    query = db.query(AudioFile).filter(AudioFile.deleted_at.is_(None))
    if mine_only:
        query = query.filter(AudioFile.user_id == current_user.user_id)
    if folder_id is not None:
        query = query.filter(AudioFile.folder_id == folder_id)
    elif root_only:
        query = query.filter(AudioFile.folder_id.is_(None))
    if q:
        pattern = f"%{q.lower()}%"
        from sqlalchemy import func as sa_func, or_
        query = query.filter(
            or_(
                sa_func.lower(AudioFile.file_name).like(pattern),
                sa_func.lower(AudioFile.topic).like(pattern),
            )
        )
    if language:
        query = query.filter(AudioFile.language == language)
    if scene:
        query = query.filter(AudioFile.scene == scene)
    if source:
        query = query.filter(AudioFile.source == source)
    if speaker_count is not None:
        query = query.filter(AudioFile.speaker_count == speaker_count)
    if duration_min is not None:
        query = query.filter(AudioFile.duration_sec >= duration_min)
    if duration_max is not None:
        query = query.filter(AudioFile.duration_sec <= duration_max)
    if date_from:
        try:
            df = _dt.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"date_from 格式不正确: {date_from}（应为 YYYY-MM-DD）"
            )
        query = query.filter(AudioFile.created_at >= df)
    if date_to:
        try:
            dt_end = _dt.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"date_to 格式不正确: {date_to}（应为 YYYY-MM-DD）"
            )
        # 截止日含当天 23:59:59
        dt_end = dt_end.replace(hour=23, minute=59, second=59)
        query = query.filter(AudioFile.created_at <= dt_end)
    if tags:
        # AND 关系：文件必须同时包含所有指定标签
        for tag_name in tags:
            if tag_name.strip():
                query = query.filter(
                    AudioFile.tags.any(Tag.name == tag_name.strip())
                )

    query = query.order_by(AudioFile.created_at.desc())
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    # has_transcript 判定优先：transcripts 表（带时间码），其次 task.dialogue_text
    file_ids = [r.file_id for r in rows]
    transcripts_set: set[uuid.UUID] = set()
    if file_ids:
        rows_t = (
            db.query(Transcript.file_id)
            .filter(Transcript.file_id.in_(file_ids))
            .all()
        )
        transcripts_set = {fid for (fid,) in rows_t}

    task_ids = [r.task_id for r in rows if r.source == "generated" and r.task_id]
    legacy_set: set[uuid.UUID] = set()
    if task_ids:
        rows_legacy = (
            db.query(Task.task_id)
            .filter(Task.task_id.in_(task_ids), Task.dialogue_text.is_not(None))
            .all()
        )
        legacy_set = {tid for (tid,) in rows_legacy}

    result = []
    for r in rows:
        out = AudioFileOut.model_validate(r)
        out.has_transcript = (
            r.file_id in transcripts_set
            or (r.task_id is not None and r.task_id in legacy_set)
        )
        result.append(out)
    return result


@router.get("/trash", response_model=list[AudioFileOut])
def list_trash(current_user: CurrentUser, db: DbSession) -> list[AudioFileOut]:
    """回收站：仅显示自己的软删除文件。"""
    rows = (
        db.query(AudioFile)
        .filter(
            AudioFile.user_id == current_user.user_id,
            AudioFile.deleted_at.is_not(None),
        )
        .order_by(AudioFile.deleted_at.desc())
        .all()
    )
    return [AudioFileOut.model_validate(r) for r in rows]


@router.get("/{file_id}", response_model=AudioFileOut)
def get_file(file_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> AudioFileOut:
    f = db.query(AudioFile).filter(AudioFile.file_id == file_id).first()
    if not f or f.deleted_at is not None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return AudioFileOut.model_validate(f)


@router.get("/{file_id}/download", response_model=AudioFileDownload)
def download_url(
    file_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    force_download: bool = Query(False, description="True = 触发浏览器另存为；False = 在线播放"),
) -> AudioFileDownload:
    """返回 MinIO 预签名 URL，前端直接 GET。PRD §4.2：任何登录用户都可下载。"""
    f = db.query(AudioFile).filter(AudioFile.file_id == file_id).first()
    if not f or f.deleted_at is not None:
        raise HTTPException(status_code=404, detail="文件不存在")

    expires = 600
    url = get_presigned_download_url(
        f.storage_key,
        expires_sec=expires,
        force_download_name=f.file_name if force_download else None,
    )
    return AudioFileDownload(file_id=f.file_id, download_url=url, expires_in_sec=expires)


@router.post("/upload", response_model=AudioFileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    language: str = Form(...),
    scene: str = Form(...),
    speaker_count: int = Form(..., ge=1, le=10),
    folder_id: uuid.UUID | None = Form(None),
    tag_names: str = Form("", description="逗号分隔的标签"),
) -> AudioFileOut:
    """PRD §13.2: 上传音频文件。WAV/MP3/M4A/MP4，单文件 ≤ 500MB。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式 {ext}，请上传 WAV / MP3 / M4A / MP4",
        )

    # 校验文件夹归属
    if folder_id is not None:
        folder = db.query(Folder).filter(Folder.folder_id == folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="目标文件夹不存在")
        if folder.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="无权上传到他人文件夹")

    # 临时落盘以便读大小 + 探测时长
    max_bytes = _settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    tmp = Path(tempfile.mkdtemp(prefix="upload_")) / f"upload{ext}"
    try:
        size = 0
        with tmp.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件大小超出限制（最大 {_settings.MAX_UPLOAD_SIZE_MB}MB）",
                    )
                f.write(chunk)

        # 探测时长（ffprobe）
        duration_sec: float | None = None
        if shutil.which("ffprobe"):
            try:
                result = subprocess.run(
                    [
                        "ffprobe", "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        str(tmp),
                    ],
                    check=True, capture_output=True, text=True, timeout=30,
                )
                duration_sec = round(float(result.stdout.strip()), 2)
            except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired):
                duration_sec = None

        # 上传到 MinIO
        file_id = uuid.uuid4()
        safe_name = file.filename.replace("/", "_").replace("\\", "_")
        storage_key = build_audio_key(str(file_id), safe_name)
        content_type = {
            ".mp3": "audio/mpeg", ".wav": "audio/wav",
            ".m4a": "audio/mp4", ".mp4": "audio/mp4",
        }.get(ext, "application/octet-stream")
        minio_upload_file(storage_key, str(tmp), content_type=content_type)

        # 入库
        af = AudioFile(
            file_id=file_id,
            user_id=current_user.user_id,
            folder_id=folder_id,
            file_name=safe_name,
            storage_key=storage_key,
            file_size=size,
            duration_sec=duration_sec,
            format=ext.lstrip("."),
            language=language,
            speaker_count=speaker_count,
            scene=scene,
            topic=Path(safe_name).stem[:255],
            source="uploaded",
        )

        # 标签
        tag_list = [t.strip() for t in tag_names.split(",") if t.strip()] if tag_names else []
        if tag_list:
            af.tags = upsert_tags_by_names(db, tag_list)

        db.add(af)
        db.commit()
        db.refresh(af)
        return AudioFileOut.model_validate(af)

    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)


class MoveRequest(BaseModel):
    folder_id: uuid.UUID | None = None  # None = 根目录
    conflict_strategy: str = "ask"  # ask / overwrite / keep_both


def _unique_file_name(db, user_id: uuid.UUID, folder_id: uuid.UUID | None, base_name: str) -> str:
    """如果同文件夹下已有同名文件，自动加 (1)/(2)/... 后缀。"""
    stem, _, ext = base_name.rpartition(".")
    if not stem:
        stem, ext = base_name, ""
    n = 1
    new_name = base_name
    while True:
        exists = (
            db.query(AudioFile.file_id)
            .filter(
                AudioFile.user_id == user_id,
                AudioFile.folder_id == folder_id,
                AudioFile.file_name == new_name,
                AudioFile.deleted_at.is_(None),
            )
            .first()
        )
        if not exists:
            return new_name
        new_name = f"{stem}({n}){'.' + ext if ext else ''}"
        n += 1


@router.post("/{file_id}/move", response_model=AudioFileOut)
def move_file(
    file_id: uuid.UUID, payload: MoveRequest, current_user: CurrentUser, db: DbSession
) -> AudioFileOut:
    """PRD §13.5: 移动文件到指定文件夹（或根目录）。仅创建者可移动。

    同名冲突处理（conflict_strategy）：
      - "ask"       默认。检测到同名时返回 409，body 含 conflict=True
      - "overwrite" 覆盖：软删除目标位置的同名文件，然后移动当前文件
      - "keep_both" 保留：当前文件改名为 name(1).ext
    """
    f = db.query(AudioFile).filter(AudioFile.file_id == file_id).first()
    if not f or f.deleted_at is not None:
        raise HTTPException(status_code=404, detail="文件不存在")
    if f.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权移动他人文件")

    if payload.folder_id is not None:
        target = db.query(Folder).filter(Folder.folder_id == payload.folder_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="目标文件夹不存在")
        if target.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="无权移动到他人文件夹")

    # 同名检测（排除自己）
    conflict = (
        db.query(AudioFile)
        .filter(
            AudioFile.user_id == current_user.user_id,
            AudioFile.folder_id == payload.folder_id,
            AudioFile.file_name == f.file_name,
            AudioFile.file_id != file_id,
            AudioFile.deleted_at.is_(None),
        )
        .first()
    )

    if conflict:
        if payload.conflict_strategy == "ask":
            raise HTTPException(
                status_code=409,
                detail={
                    "conflict": True,
                    "file_name": f.file_name,
                    "target_folder_id": str(payload.folder_id) if payload.folder_id else None,
                    "message": "目标位置已存在同名文件",
                },
            )
        elif payload.conflict_strategy == "overwrite":
            # 软删冲突的那个
            from datetime import datetime as _dt3, timezone as _tz
            conflict.deleted_at = _dt3.now(tz=_tz.utc)
        elif payload.conflict_strategy == "keep_both":
            f.file_name = _unique_file_name(db, current_user.user_id, payload.folder_id, f.file_name)
        else:
            raise HTTPException(status_code=400, detail=f"未知的冲突策略: {payload.conflict_strategy}")

    f.folder_id = payload.folder_id
    db.commit()
    db.refresh(f)
    return AudioFileOut.model_validate(f)


@router.patch("/{file_id}", response_model=AudioFileOut)
def update_file(
    file_id: uuid.UUID, payload: AudioFileUpdate, current_user: CurrentUser, db: DbSession
) -> AudioFileOut:
    """PRD §15：详情页编辑文件名 / 语言 / 人数 / 场景 / 标签。仅创建者可编辑。"""
    f = db.query(AudioFile).filter(AudioFile.file_id == file_id).first()
    if not f or f.deleted_at is not None:
        raise HTTPException(status_code=404, detail="文件不存在")
    if f.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权编辑他人文件")

    if payload.file_name is not None:
        f.file_name = payload.file_name.strip()
    if payload.language is not None:
        f.language = payload.language
    if payload.speaker_count is not None:
        f.speaker_count = payload.speaker_count
    if payload.scene is not None:
        f.scene = payload.scene
    if payload.tag_names is not None:
        # 整体覆盖
        tags = upsert_tags_by_names(db, payload.tag_names)
        f.tags = tags

    db.commit()
    db.refresh(f)
    return AudioFileOut.model_validate(f)


@router.get("/{file_id}/transcript", response_model=TranscriptResponse)
def get_transcript(
    file_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> TranscriptResponse:
    """对话脚本：优先从 transcripts 表（带时间码），降级到 task.dialogue_text。"""
    f = db.query(AudioFile).filter(AudioFile.file_id == file_id).first()
    if not f or f.deleted_at is not None:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 从关联任务提取 voice_names（speaker_id -> voice_name）
    def _get_voice_names(task_id) -> dict[str, str]:
        if not task_id:
            return {}
        try:
            tk = db.query(Task).filter(Task.task_id == task_id).first()
            if not tk:
                return {}
            assignments = (tk.params or {}).get("voice_assignments") or {}
            return {sid: v.get("voice_name", "") for sid, v in assignments.items() if v.get("voice_name")}
        except Exception:
            return {}

    # 优先：transcripts 表（合成时记录了段级 timing）
    t = db.query(Transcript).filter(Transcript.file_id == file_id).first()
    if t and t.segments:
        lines = [
            TranscriptLine(
                speaker_id=s.get("speaker_id", ""),
                text=s.get("text", ""),
                start_time=s.get("start_time"),
                end_time=s.get("end_time"),
            )
            for s in t.segments
        ]
        return TranscriptResponse(
            file_id=file_id,
            has_transcript=True,
            lines=lines,
            has_json=bool(t.json_storage_key),
            has_srt=bool(t.srt_storage_key),
            json_download_url=(
                get_presigned_download_url(t.json_storage_key, expires_sec=600)
                if t.json_storage_key else None
            ),
            srt_download_url=(
                get_presigned_download_url(t.srt_storage_key, expires_sec=600)
                if t.srt_storage_key else None
            ),
            voice_names=_get_voice_names(f.task_id),
        )

    # 降级：解析 task.dialogue_text（老数据，无时间码）
    if f.source != "generated" or not f.task_id:
        return TranscriptResponse(file_id=file_id, has_transcript=False, lines=[])
    task = db.query(Task).filter(Task.task_id == f.task_id).first()
    if not task or not task.dialogue_text:
        return TranscriptResponse(file_id=file_id, has_transcript=False, lines=[])
    try:
        parsed = parse_manual_dialogue(task.dialogue_text)
    except ValueError:
        return TranscriptResponse(file_id=file_id, has_transcript=False, lines=[])
    lines = [TranscriptLine(speaker_id=sid, text=text) for sid, text in parsed]
    return TranscriptResponse(
        file_id=file_id, has_transcript=True, lines=lines,
        voice_names=_get_voice_names(f.task_id),
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete(file_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """软删除。PRD §4.2：只能删自己的。"""
    f = db.query(AudioFile).filter(AudioFile.file_id == file_id).first()
    if not f or f.deleted_at is not None:
        raise HTTPException(status_code=404, detail="文件不存在")
    if f.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权删除他人文件")
    f.deleted_at = datetime.now(timezone.utc)
    db.commit()


@router.post("/{file_id}/restore", response_model=AudioFileOut)
def restore_file(
    file_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> AudioFileOut:
    f = db.query(AudioFile).filter(AudioFile.file_id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")
    if f.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权操作他人文件")
    f.deleted_at = None
    db.commit()
    db.refresh(f)
    return AudioFileOut.model_validate(f)


@router.delete("/{file_id}/purge", status_code=status.HTTP_204_NO_CONTENT)
def purge_file(file_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """PRD §13.4: 永久删除。先删 MinIO 对象，再删 DB 记录。"""
    f = db.query(AudioFile).filter(AudioFile.file_id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")
    if f.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权操作他人文件")
    try:
        delete_object(f.storage_key)
    except Exception:
        # MinIO 失败不阻塞 DB 删除（孤儿对象后续清理 job 处理）
        pass
    db.delete(f)
    db.commit()


# ============ 批量操作 ============
class BatchIds(BaseModel):
    file_ids: list[uuid.UUID]


class BatchMove(BatchIds):
    folder_id: uuid.UUID | None = None


@router.post("/batch/move", status_code=status.HTTP_200_OK)
def batch_move(payload: BatchMove, current_user: CurrentUser, db: DbSession) -> dict:
    """PRD §13.5: 批量移动到指定文件夹。"""
    if payload.folder_id is not None:
        target = db.query(Folder).filter(Folder.folder_id == payload.folder_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="目标文件夹不存在")
        if target.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="无权移动到他人文件夹")
    updated = (
        db.query(AudioFile)
        .filter(
            AudioFile.file_id.in_(payload.file_ids),
            AudioFile.user_id == current_user.user_id,
            AudioFile.deleted_at.is_(None),
        )
        .update({AudioFile.folder_id: payload.folder_id}, synchronize_session=False)
    )
    db.commit()
    return {"moved": updated}


@router.post("/batch/delete", status_code=status.HTTP_200_OK)
def batch_soft_delete(payload: BatchIds, current_user: CurrentUser, db: DbSession) -> dict:
    """批量软删除。"""
    now = _dt.now(tz=None).astimezone()
    deleted = (
        db.query(AudioFile)
        .filter(
            AudioFile.file_id.in_(payload.file_ids),
            AudioFile.user_id == current_user.user_id,
            AudioFile.deleted_at.is_(None),
        )
        .update({AudioFile.deleted_at: now}, synchronize_session=False)
    )
    db.commit()
    return {"deleted": deleted}


@router.post("/batch/restore", status_code=status.HTTP_200_OK)
def batch_restore(payload: BatchIds, current_user: CurrentUser, db: DbSession) -> dict:
    restored = (
        db.query(AudioFile)
        .filter(
            AudioFile.file_id.in_(payload.file_ids),
            AudioFile.user_id == current_user.user_id,
            AudioFile.deleted_at.is_not(None),
        )
        .update({AudioFile.deleted_at: None}, synchronize_session=False)
    )
    db.commit()
    return {"restored": restored}


@router.post("/batch/download")
def batch_download(payload: BatchIds, current_user: CurrentUser, db: DbSession):
    """PRD §13.3: 批量打 ZIP 下载。限制 50 个 / 2GB。"""
    if len(payload.file_ids) == 0:
        raise HTTPException(status_code=400, detail="未选择任何文件")
    if len(payload.file_ids) > 50:
        raise HTTPException(status_code=400, detail="单次最多支持 50 个文件")

    rows = (
        db.query(AudioFile)
        .filter(
            AudioFile.file_id.in_(payload.file_ids),
            AudioFile.deleted_at.is_(None),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="未找到可下载的文件")

    total_size = sum(r.file_size or 0 for r in rows)
    if total_size > 2 * 1024 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"所选文件总大小 {total_size / 1024 / 1024 / 1024:.2f}GB 超过 2GB 限制",
        )

    import io
    import zipfile
    from datetime import datetime as _dt2

    def stream_zip():
        """流式生成 ZIP（边读 MinIO 边压缩）。"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_STORED) as zf:
            used_names: set[str] = set()
            for f in rows:
                # 避免 zip 内重名
                name = f.file_name
                base = name.rsplit(".", 1)
                stem, ext = base if len(base) == 2 else (name, "")
                idx = 1
                while name in used_names:
                    name = f"{stem}({idx}){'.' + ext if ext else ''}"
                    idx += 1
                used_names.add(name)

                try:
                    obj = get_object_stream(f.storage_key)
                    data = obj.read()
                    obj.close()
                    obj.release_conn()
                except Exception as e:
                    logger.warning(f"Failed to fetch {f.storage_key}: {e}")
                    continue
                zf.writestr(name, data)
        buf.seek(0)
        yield from iter(lambda: buf.read(64 * 1024), b"")

    ts = _dt2.now().strftime("%Y%m%d%H%M%S")
    return StreamingResponse(
        stream_zip(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="audio_export_{ts}.zip"',
        },
    )


@router.post("/batch/purge", status_code=status.HTTP_200_OK)
def batch_purge(payload: BatchIds, current_user: CurrentUser, db: DbSession) -> dict:
    """批量永久删除。"""
    rows = (
        db.query(AudioFile)
        .filter(
            AudioFile.file_id.in_(payload.file_ids),
            AudioFile.user_id == current_user.user_id,
        )
        .all()
    )
    count = 0
    for f in rows:
        try:
            delete_object(f.storage_key)
        except Exception:
            pass
        db.delete(f)
        count += 1
    db.commit()
    return {"purged": count}
