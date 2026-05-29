"""认证：注册 / 登录 / 当前用户。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from loguru import logger

import re

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.user import GoogleLogin, LoginResponse, UserLogin, UserOut, UserRegister

settings = get_settings()

router = APIRouter()


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: DbSession) -> LoginResponse:
    """PRD §4.1：注册成功后自动登录。"""
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.user_id))
    logger.info(f"User registered: {user.username} ({user.user_id})")
    return LoginResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=LoginResponse)
def login(payload: UserLogin, db: DbSession) -> LoginResponse:
    """PRD §4.1：失败统一提示"用户名或密码错误"，不区分。"""
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已停用",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(subject=str(user.user_id))
    logger.info(f"User logged in: {user.username}")
    return LoginResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/sso/config")
def sso_config() -> dict:
    """前端登录页用这个判断要不要显示 Google 按钮 + 拿 Client ID。"""
    return {
        "google_enabled": bool(settings.GOOGLE_CLIENT_ID),
        "google_client_id": settings.GOOGLE_CLIENT_ID or None,
        "allowed_domain": settings.GOOGLE_ALLOWED_DOMAIN or None,
    }


@router.post("/google", response_model=LoginResponse)
def google_login(payload: GoogleLogin, db: DbSession) -> LoginResponse:
    """Google SSO 登录/注册一体化。

    流程：
      1. 前端用 Google Identity Services 拿到 ID token
      2. 后端用 google-auth 验签 + 校验 aud/iss
      3. 校验邮箱域名 = GOOGLE_ALLOWED_DOMAIN（默认 plaud.ai）
      4. 按 google_id 找用户；找不到再按 email 找；都没有则新建
      5. 签发 JWT 返回
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google SSO 未启用（管理员未配置 GOOGLE_CLIENT_ID）",
        )

    # 1. 验签
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token as g_id_token

    try:
        info = g_id_token.verify_oauth2_token(
            payload.id_token,
            g_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        logger.warning(f"Google ID token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Google 凭据无效或已过期") from e

    # 2. 解析关键字段
    google_id = info.get("sub")
    email: str = (info.get("email") or "").lower()
    name = info.get("name") or info.get("given_name") or ""
    picture = info.get("picture")
    email_verified = info.get("email_verified", False)
    hd = info.get("hd")  # Workspace 域名

    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Google 凭据缺少必要信息")
    if not email_verified:
        raise HTTPException(status_code=403, detail="Google 邮箱未验证，无法登录")

    # 3. 域名限制：hd 字段 OR email 后缀
    allowed = settings.GOOGLE_ALLOWED_DOMAIN.lower()
    if allowed:
        domain_ok = (hd or "").lower() == allowed or email.endswith(f"@{allowed}")
        if not domain_ok:
            raise HTTPException(
                status_code=403,
                detail=f"仅允许 @{allowed} 域账号登录",
            )

    # 4. 查找/创建用户
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        # 按 email 找：可能用户已用密码注册过，自动绑定 google_id
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id
            if picture and not user.avatar_url:
                user.avatar_url = picture
        else:
            # 新用户：根据邮箱前缀生成 username
            base = re.sub(r"[^A-Za-z0-9_]", "_", email.split("@")[0])[:18] or "user"
            username = base
            n = 2
            while db.query(User.user_id).filter(User.username == username).first():
                username = f"{base}{n}"
                n += 1
                if len(username) > 20:
                    base = base[:16]
                    username = f"{base}{n}"
            user = User(
                username=username,
                password_hash=None,  # SSO 用户无密码
                display_name=name[:50] or username,
                email=email,
                google_id=google_id,
                avatar_url=picture,
            )
            db.add(user)
            logger.info(f"New SSO user created: {username} ({email})")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.user_id))
    logger.info(f"User logged in via Google: {user.username}")
    return LoginResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)
