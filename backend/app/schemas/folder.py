"""文件夹 Pydantic 模型。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None  # 二期再支持移动文件夹本身


class FolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    folder_id: uuid.UUID
    user_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    depth: int
    created_at: datetime


class FolderTreeNode(FolderOut):
    """带子节点的树形结构。"""
    children: list["FolderTreeNode"] = []
    file_count: int = 0  # 该文件夹下未删除的文件数（不含子文件夹）


FolderTreeNode.model_rebuild()
