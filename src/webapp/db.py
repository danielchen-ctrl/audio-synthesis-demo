"""
webapp/db.py
============
SQLite 数据库初始化与 CRUD 辅助函数。
数据库文件位于 runtime/platform.db，Python 内置 sqlite3，零配置，首次启动自动创建。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "runtime" / "platform.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id         TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'queued',
    generation_mode TEXT NOT NULL DEFAULT 'llm',
    topic           TEXT,
    language        TEXT,
    people_count    INTEGER,
    word_count      INTEGER,
    template        TEXT,
    keywords        TEXT DEFAULT '[]',
    custom_prompt   TEXT,
    input_text      TEXT,
    voice_map       TEXT DEFAULT '{}',
    output_format   TEXT DEFAULT 'mp3',
    include_scripts INTEGER DEFAULT 0,
    error_msg       TEXT,
    file_id         TEXT,
    dialogue_id     TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS audio_files (
    file_id         TEXT PRIMARY KEY,
    task_id         TEXT,
    file_name       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'generated',
    duration        REAL,
    format          TEXT,
    file_size       INTEGER,
    language        TEXT,
    speaker_count   INTEGER,
    scene           TEXT DEFAULT 'other',
    topic           TEXT,
    transcript_json TEXT,
    transcript_srt  TEXT,
    tags            TEXT DEFAULT '[]',
    folder_id       TEXT,
    deleted         INTEGER DEFAULT 0,
    deleted_at      TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS folders (
    folder_id  TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    parent_id  TEXT,
    created_at TEXT NOT NULL
);
"""


# ── 连接 ──────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _add_column_if_missing(conn: sqlite3.Connection, table: str, col: str, col_def: str) -> bool:
    """如果列不存在则 ALTER TABLE 添加，已存在直接返回 False。"""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {r["name"] for r in rows}
    if col not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
        return True
    return False


def _run_tts_migration(conn: sqlite3.Connection) -> bool:
    """
    幂等迁移：为 tasks / audio_files 表补充真人 TTS 相关列。
    返回 True 表示本次执行了至少一处变更。
    """
    changed = False
    changed |= _add_column_if_missing(conn, "tasks", "tts_provider",
                                      "TEXT DEFAULT 'edge_tts'")
    changed |= _add_column_if_missing(conn, "tasks", "tts_fallback_strategy",
                                      "TEXT DEFAULT 'edge_then_bundle'")
    changed |= _add_column_if_missing(conn, "tasks", "voice_assignments",
                                      "TEXT DEFAULT '{}'")
    changed |= _add_column_if_missing(conn, "audio_files", "tts_meta",
                                      "TEXT DEFAULT NULL")
    return changed


def init_db() -> None:
    """创建数据库文件并初始化表结构（幂等），并执行 TTS 列迁移。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.executescript(_SCHEMA)
        _run_tts_migration(c)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:16]


# ── tasks CRUD ────────────────────────────────────────────────────────────────

def create_task(data: dict) -> dict:
    tid = new_id()
    now = now_iso()
    # voice_assignments 接受 dict 或 JSON 字符串
    va = data.get("voice_assignments", {})
    if isinstance(va, dict):
        va = json.dumps(va, ensure_ascii=False)
    with _conn() as c:
        c.execute(
            """
            INSERT INTO tasks
                (task_id, status, generation_mode, topic, language, people_count,
                 word_count, template, keywords, custom_prompt, input_text,
                 voice_map, output_format, include_scripts,
                 tts_provider, tts_fallback_strategy, voice_assignments,
                 created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                tid,
                "queued",
                data.get("generation_mode", "llm"),
                data.get("topic"),
                data.get("language", "中文"),
                int(data.get("people_count", 2)),
                int(data.get("word_count", 1000)),
                data.get("template"),
                json.dumps(data.get("keywords", []), ensure_ascii=False),
                data.get("custom_prompt"),
                data.get("input_text"),
                json.dumps(data.get("voice_map", {}), ensure_ascii=False),
                data.get("output_format", "mp3"),
                1 if data.get("include_scripts") else 0,
                data.get("tts_provider", "edge_tts"),
                data.get("tts_fallback_strategy", "edge_then_bundle"),
                va,
                now,
                now,
            ),
        )
    return get_task(tid)


def get_task(task_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    return dict(row) if row else None


def list_tasks(limit: int = 50, offset: int = 0) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """SELECT t.*, af.duration AS file_duration
               FROM tasks t
               LEFT JOIN audio_files af ON t.file_id = af.file_id
               ORDER BY t.created_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def count_active_tasks() -> int:
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) FROM tasks WHERE status IN ('queued','generating_text','synthesizing')"
        ).fetchone()
    return row[0] if row else 0


def update_task_status(task_id: str, status: str, **kwargs) -> None:
    now = now_iso()
    fields: dict = {"status": status, "updated_at": now}
    if status == "completed":
        fields["completed_at"] = now
    fields.update(kwargs)
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [task_id]
    with _conn() as c:
        c.execute(f"UPDATE tasks SET {set_clause} WHERE task_id=?", values)


def delete_task(task_id: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM tasks WHERE task_id=?", (task_id,))


def retry_task(task_id: str) -> dict | None:
    """将失败任务重置为 queued，清空错误信息。"""
    now = now_iso()
    with _conn() as c:
        c.execute(
            "UPDATE tasks SET status='queued', error_msg=NULL, file_id=NULL, "
            "dialogue_id=NULL, updated_at=? WHERE task_id=? AND status='failed'",
            (now, task_id),
        )
    return get_task(task_id)


def delete_completed_tasks() -> int:
    """删除所有已完成任务，返回删除数量。"""
    with _conn() as c:
        cur = c.execute("DELETE FROM tasks WHERE status='completed'")
        return cur.rowcount


# ── audio_files CRUD ──────────────────────────────────────────────────────────

def create_audio_file(data: dict) -> dict:
    fid = new_id()
    now = now_iso()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO audio_files
                (file_id, task_id, file_name, file_path, source, duration, format,
                 file_size, language, speaker_count, scene, topic,
                 transcript_json, transcript_srt, tags, folder_id, tts_meta, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                fid,
                data.get("task_id"),
                data["file_name"],
                data["file_path"],
                data.get("source", "generated"),
                data.get("duration"),
                data.get("format"),
                data.get("file_size"),
                data.get("language"),
                data.get("speaker_count"),
                data.get("scene", "other"),
                data.get("topic"),
                data.get("transcript_json"),
                data.get("transcript_srt"),
                json.dumps(data.get("tags", []), ensure_ascii=False),
                data.get("folder_id"),
                data.get("tts_meta"),   # JSON str | None
                now,
            ),
        )
    return get_audio_file(fid)


def get_audio_file(file_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM audio_files WHERE file_id=?", (file_id,)
        ).fetchone()
    return dict(row) if row else None


def list_audio_files(
    folder_id: str | None = "_unset_",
    include_deleted: bool = False,
    search: str = "",
    language: str = "",
    scene: str = "",
    source: str = "",
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    conds = []
    params: list = []

    if include_deleted:
        conds.append("deleted=1")
    else:
        conds.append("deleted=0")

    # folder_id=None means "root (no folder)", omit param to get all
    if folder_id != "_unset_":
        if folder_id is None:
            conds.append("folder_id IS NULL")
        else:
            conds.append("folder_id=?")
            params.append(folder_id)

    if search:
        conds.append("(file_name LIKE ? OR topic LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]
    if language:
        conds.append("language=?")
        params.append(language)
    if scene:
        conds.append("scene=?")
        params.append(scene)
    if source:
        conds.append("source=?")
        params.append(source)

    where = " AND ".join(conds) if conds else "1=1"
    with _conn() as c:
        rows = c.execute(
            f"SELECT * FROM audio_files WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    return [dict(r) for r in rows]


def count_audio_files(include_deleted: bool = False) -> int:
    deleted_val = 1 if include_deleted else 0
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) FROM audio_files WHERE deleted=?", (deleted_val,)
        ).fetchone()
    return row[0] if row else 0


def update_audio_file(file_id: str, **kwargs) -> None:
    if not kwargs:
        return
    set_clause = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [file_id]
    with _conn() as c:
        c.execute(f"UPDATE audio_files SET {set_clause} WHERE file_id=?", values)


def soft_delete_file(file_id: str) -> None:
    now = now_iso()
    with _conn() as c:
        c.execute(
            "UPDATE audio_files SET deleted=1, deleted_at=? WHERE file_id=?",
            (now, file_id),
        )


def restore_file(file_id: str) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE audio_files SET deleted=0, deleted_at=NULL WHERE file_id=?",
            (file_id,),
        )


def hard_delete_file(file_id: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM audio_files WHERE file_id=?", (file_id,))


def move_file(file_id: str, folder_id: str | None) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE audio_files SET folder_id=? WHERE file_id=?",
            (folder_id, file_id),
        )


# ── folders CRUD ──────────────────────────────────────────────────────────────

def create_folder(name: str, parent_id: str | None = None) -> dict:
    fid = new_id()
    now = now_iso()
    with _conn() as c:
        c.execute(
            "INSERT INTO folders (folder_id, name, parent_id, created_at) VALUES (?,?,?,?)",
            (fid, name, parent_id, now),
        )
    return get_folder(fid)


def get_folder(folder_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM folders WHERE folder_id=?", (folder_id,)
        ).fetchone()
    return dict(row) if row else None


def list_folders(parent_id: str | None = None, _all: bool = False) -> list[dict]:
    with _conn() as c:
        if _all:
            rows = c.execute("SELECT * FROM folders ORDER BY name").fetchall()
        elif parent_id is None:
            rows = c.execute(
                "SELECT * FROM folders WHERE parent_id IS NULL ORDER BY name"
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM folders WHERE parent_id=? ORDER BY name", (parent_id,)
            ).fetchall()
    return [dict(r) for r in rows]


def rename_folder(folder_id: str, name: str) -> None:
    with _conn() as c:
        c.execute("UPDATE folders SET name=? WHERE folder_id=?", (name, folder_id))


def delete_folder(folder_id: str) -> None:
    """软删除文件夹内文件，然后删除文件夹。"""
    now = now_iso()
    with _conn() as c:
        c.execute(
            "UPDATE audio_files SET deleted=1, deleted_at=? WHERE folder_id=? AND deleted=0",
            (now, folder_id),
        )
        c.execute("DELETE FROM folders WHERE folder_id=?", (folder_id,))
