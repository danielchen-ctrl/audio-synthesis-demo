"""文件夹 CRUD：仅自己的文件夹（PRD §4.2）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func

from app.api.deps import CurrentUser, DbSession
from app.models import AudioFile, Folder
from app.schemas.folder import FolderCreate, FolderOut, FolderTreeNode, FolderUpdate

router = APIRouter()

MAX_DEPTH = 2  # 根目录 depth=0，一级=1，二级=2 → 最多 3 层


@router.get("", response_model=list[FolderTreeNode])
def list_folders(current_user: CurrentUser, db: DbSession) -> list[FolderTreeNode]:
    """返回当前用户的文件夹树形结构。"""
    folders = (
        db.query(Folder)
        .filter(Folder.user_id == current_user.user_id)
        .order_by(Folder.name)
        .all()
    )

    # 统计每个文件夹下的文件数（非递归，只算直接子文件）
    counts = (
        db.query(AudioFile.folder_id, func.count(AudioFile.file_id))
        .filter(
            AudioFile.user_id == current_user.user_id,
            AudioFile.deleted_at.is_(None),
            AudioFile.folder_id.is_not(None),
        )
        .group_by(AudioFile.folder_id)
        .all()
    )
    count_map = {fid: c for fid, c in counts}

    # 构建树
    nodes: dict[uuid.UUID, FolderTreeNode] = {}
    for f in folders:
        node = FolderTreeNode.model_validate(f)
        node.file_count = count_map.get(f.folder_id, 0)
        nodes[f.folder_id] = node

    roots: list[FolderTreeNode] = []
    for f in folders:
        node = nodes[f.folder_id]
        if f.parent_id and f.parent_id in nodes:
            nodes[f.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: FolderCreate, current_user: CurrentUser, db: DbSession
) -> FolderOut:
    """PRD §13.6: 最多 3 层嵌套，同级不能重名。"""
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="文件夹名不能为空")

    depth = 0
    if payload.parent_id:
        parent = db.query(Folder).filter(Folder.folder_id == payload.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父文件夹不存在")
        if parent.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="无权在他人文件夹下创建")
        if parent.depth >= MAX_DEPTH:
            raise HTTPException(status_code=400, detail="最多支持 3 层嵌套")
        depth = parent.depth + 1

    # 同级重名检查
    dupe = (
        db.query(Folder)
        .filter(
            Folder.user_id == current_user.user_id,
            Folder.parent_id == payload.parent_id,
            Folder.name == name,
        )
        .first()
    )
    if dupe:
        raise HTTPException(status_code=409, detail="同级目录下已有同名文件夹")

    folder = Folder(
        user_id=current_user.user_id,
        parent_id=payload.parent_id,
        name=name,
        depth=depth,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return FolderOut.model_validate(folder)


@router.patch("/{folder_id}", response_model=FolderOut)
def update_folder(
    folder_id: uuid.UUID,
    payload: FolderUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> FolderOut:
    """重命名文件夹。"""
    folder = db.query(Folder).filter(Folder.folder_id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    if folder.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权操作他人文件夹")

    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="文件夹名不能为空")
        # 同级重名检查（排除自己）
        dupe = (
            db.query(Folder)
            .filter(
                Folder.user_id == current_user.user_id,
                Folder.parent_id == folder.parent_id,
                Folder.name == new_name,
                Folder.folder_id != folder_id,
            )
            .first()
        )
        if dupe:
            raise HTTPException(status_code=409, detail="同级目录下已有同名文件夹")
        folder.name = new_name

    db.commit()
    db.refresh(folder)
    return FolderOut.model_validate(folder)


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    """删除文件夹：文件夹内所有文件（含子文件夹的递归）软删除到回收站。

    DB FK ON DELETE CASCADE 会删除子文件夹本身（folders 表）。
    audio_files.folder_id ON DELETE SET NULL → 文件 folder_id 置空，再手动标 deleted_at。
    """
    folder = db.query(Folder).filter(Folder.folder_id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    if folder.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权操作他人文件夹")

    # 收集要删除的文件夹 ID 集合（递归）
    to_delete: set[uuid.UUID] = set()
    stack: list[uuid.UUID] = [folder_id]
    while stack:
        cur = stack.pop()
        to_delete.add(cur)
        children = (
            db.query(Folder.folder_id)
            .filter(Folder.parent_id == cur)
            .all()
        )
        stack.extend(c[0] for c in children)

    # 软删文件夹内所有文件
    now = datetime.now(timezone.utc)
    db.query(AudioFile).filter(
        AudioFile.user_id == current_user.user_id,
        AudioFile.folder_id.in_(to_delete),
        AudioFile.deleted_at.is_(None),
    ).update({AudioFile.deleted_at: now}, synchronize_session=False)

    # 删文件夹本身（CASCADE 会递归删子）
    db.delete(folder)
    db.commit()
