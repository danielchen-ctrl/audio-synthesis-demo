"""管理类 API：诊断、缓存重载等。

权限：当前 PRD 不区分角色（§4.2），所有登录用户都能调；
后续二期加 admin role 时只需替换 dependency。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.services import few_shot

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/server-info")
def server_info(current_user: CurrentUser) -> dict:
    """返回服务器局域网 IP，供前端生成可分享的访问链接。"""
    import socket
    ips = []
    try:
        # 连接外部地址获取出口 IP（不发送数据）
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
    except Exception:
        pass
    # 兜底：getaddrinfo
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return {"lan_ips": ips, "frontend_port": 5173}


@router.get("/few-shot/stats")
def few_shot_stats(current_user: CurrentUser) -> dict:
    """Few-shot 索引概览：总数 / 分数分布 / 按语言/按主题分组。"""
    return few_shot.stats()


@router.post("/voices/sync-from-cosyvoice")
def sync_voices_from_cosyvoice(current_user: CurrentUser, db: DbSession) -> dict:
    """从 CosyVoice /v1/voices/custom 拉取全量音色，同步写入 voice_catalog 表。

    已存在的 voice_id 只更新 is_deleted=False（恢复软删除），不覆盖名称。
    返回 {created, restored, skipped, errors}。
    """
    from app.models.voice_catalog import VoiceCatalog
    from app.providers.tts.factory import get_tts_provider

    tts = get_tts_provider()
    remote_voices = tts.list_voices()

    created = restored = skipped = errors = 0
    for v in remote_voices:
        if not v.voice_id:
            errors += 1
            continue
        try:
            existing = db.query(VoiceCatalog).filter_by(voice_id=v.voice_id).first()
            if existing:
                if existing.is_deleted:
                    existing.is_deleted = False
                    restored += 1
                else:
                    skipped += 1
            else:
                db.add(VoiceCatalog(
                    voice_id=v.voice_id,
                    name=v.name,
                    language=v.language or "zh",
                    gender=v.gender,
                    created_by=current_user.user_id,
                ))
                created += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"sync voice {v.voice_id} failed: {exc}")
            errors += 1

    db.commit()
    logger.info(f"Voice sync: created={created} restored={restored} skipped={skipped} errors={errors}")
    return {"created": created, "restored": restored, "skipped": skipped, "errors": errors, "total_remote": len(remote_voices)}


@router.post("/few-shot/reload")
def few_shot_reload(current_user: CurrentUser) -> dict:
    """清缓存重新扫目录，加完新样本时调一次（无需重启服务）。"""
    result = few_shot.reload_index()
    return {"reloaded": True, **result}
