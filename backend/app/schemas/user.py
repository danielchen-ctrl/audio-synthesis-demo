"""用户相关 Pydantic 模型。"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=6, max_length=30)
    display_name: str | None = Field(default=None, max_length=50)

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str) -> str:
        if not USERNAME_RE.match(v):
            raise ValueError("用户名仅支持字母/数字/下划线，长度 3-20")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class GoogleLogin(BaseModel):
    id_token: str  # 前端从 Google Identity Services 拿到的 ID token


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    username: str
    display_name: str | None
    created_at: datetime
    email: str | None = None
    avatar_url: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
