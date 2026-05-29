"""Tag 操作辅助。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Tag


def upsert_tags_by_names(db: Session, names: list[str]) -> list[Tag]:
    """传入一组标签名，已存在则复用，不存在则新建。返回 Tag 对象列表。"""
    clean = []
    seen: set[str] = set()
    for n in names:
        n = (n or "").strip()
        if n and n not in seen:
            seen.add(n)
            clean.append(n[:50])

    if not clean:
        return []

    # 一次性查已存在的
    existing = db.query(Tag).filter(Tag.name.in_(clean)).all()
    existing_by_name = {t.name: t for t in existing}

    result: list[Tag] = []
    for name in clean:
        if name in existing_by_name:
            result.append(existing_by_name[name])
        else:
            t = Tag(name=name)
            db.add(t)
            db.flush()  # 拿到 tag_id
            result.append(t)
    return result
