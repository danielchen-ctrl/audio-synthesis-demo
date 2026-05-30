"""音色目录 API。

GET    /api/v1/voices                 列出所有未删除音色（可按语言过滤）
POST   /api/v1/voices                 注册新音色（含强制 E2E 合成验证）
DELETE /api/v1/voices/{voice_id}      删除音色（仅创建者）

音色为全局共享：所有登录用户可查看使用，仅创建者可删除。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.models.voice_catalog import VoiceCatalog
from app.schemas.voice import VoiceCreateResponse, VoiceOut

router = APIRouter()
logger = logging.getLogger(__name__)

# 各语言的 E2E 验证短句
_VERIFY_TEXT: dict[str, str] = {
    "zh": "你好，这是音色验证。",
    "en": "Hello, this is a voice verification.",
    "ja": "こんにちは、これは音声確認です。",
    "ko": "안녕하세요, 음성 확인입니다.",
    "es": "Hola, esta es una verificación de voz.",
    "fr": "Bonjour, c'est une vérification vocale.",
    "de": "Hallo, das ist eine Sprachverifizierung.",
    "pt": "Olá, esta é uma verificação de voz.",
    "it": "Ciao, questa è una verifica vocale.",
    "ru": "Привет, это проверка голоса.",
    "ar": "مرحبا، هذا التحقق من الصوت.",
    "id": "Halo, ini adalah verifikasi suara.",
}


@router.get("", response_model=list[VoiceOut])
def list_voices(
    language: str | None = Query(None, description="按语言过滤，如 zh / en"),
    current_user: CurrentUser = ...,
    db: DbSession = ...,
) -> list[VoiceOut]:
    """列出所有可用音色（全局共享，所有用户可见）。"""
    q = db.query(VoiceCatalog).filter_by(is_deleted=False)
    if language:
        q = q.filter_by(language=language)
    return q.order_by(VoiceCatalog.created_at).all()


@router.post("", response_model=VoiceCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_voice(
    audio: UploadFile,
    name: str = Query(..., description="音色名称，如「耿同学」"),
    language: str = Query(..., description="语言代码：zh / en / ..."),
    gender: str | None = Query(None, description="male / female / neutral"),
    reference_text: str | None = Query(None, description="参考音频对应文本（可选）"),
    current_user: CurrentUser = ...,
    db: DbSession = ...,
) -> VoiceCreateResponse:
    """注册新克隆音色。

    流程：
    1. 调 CosyVoice /v1/voices/create 获取 voice_id
    2. 立即合成验证短句（E2E 验证）
    3. 验证成功 → 写 DB → 返回 201
    4. 验证失败 → 不写 DB → 返回 422
    """
    import httpx
    from app.core.config import get_settings
    from app.providers.tts.base import SynthesisRequest
    from app.providers.tts.factory import get_tts_provider

    settings = get_settings()
    base_url = settings.COSYVOICE_BASE_URL.rstrip("/")
    audio_bytes = await audio.read()

    # ── 预处理：任何格式统一转为 16kHz mono WAV ───────────────────────────────
    # CosyVoice Speaker Encoder 要求单声道输入，MP4/MP3 双声道压缩格式会导致
    # Embedding 提取失败（HTTP 500）。移植自 V1 VoiceCreateHandler 的预处理逻辑。
    import os, subprocess, tempfile, shutil as _shutil
    wav_bytes = audio_bytes  # 转换失败时回退原始
    _tmp_in = _tmp_out = None
    try:
        _suffix = os.path.splitext(audio.filename or "audio.mp4")[-1] or ".tmp"
        with tempfile.NamedTemporaryFile(suffix=_suffix, delete=False) as f:
            f.write(audio_bytes)
            _tmp_in = f.name
        _tmp_out = _tmp_in + "_16k_mono.wav"
        _ffmpeg = _shutil.which("ffmpeg") or "ffmpeg"
        _r = subprocess.run(
            [_ffmpeg, "-y", "-i", _tmp_in, "-ar", "16000", "-ac", "1", "-f", "wav", _tmp_out],
            capture_output=True, timeout=60,
        )
        if _r.returncode == 0 and os.path.getsize(_tmp_out) > 100:
            with open(_tmp_out, "rb") as f:
                wav_bytes = f.read()
            logger.info("Voice audio converted to 16kHz mono WAV (%d bytes)", len(wav_bytes))
        else:
            logger.warning("ffmpeg conversion failed (rc=%d), using raw audio", _r.returncode)
    except Exception as _e:
        logger.warning("Audio preprocessing failed, using raw audio: %s", _e)
    finally:
        for _p in (_tmp_in, _tmp_out):
            if _p:
                try:
                    os.unlink(_p)
                except Exception:
                    pass

    # ── 步骤 1：调 CosyVoice 注册音色（发送转换后的 WAV）──────────────────────
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/v1/voices/create",
                files={"audio": ("reference.wav", wav_bytes, "audio/wav")},
                data={"name": name, **({"text": reference_text} if reference_text else {})},
            )
        resp.raise_for_status()
    except Exception as exc:
        logger.exception("CosyVoice /v1/voices/create failed")
        raise HTTPException(status_code=502, detail=f"CosyVoice 服务异常，无法注册音色: {exc}") from exc

    # 解析 voice_id（兼容多种响应格式）
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    voice_id = (
        data.get("voice_id")
        or data.get("id")
        or (data.get("voice") or {}).get("id")
        or data.get("data", {}).get("voice_id")
        or ""
    )
    # voice_id 兜底：从 /v1/voices/custom 取最新一条（V1 同款兜底逻辑）
    if not voice_id:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{base_url}/v1/voices/custom")
            r.raise_for_status()
            voices_list = r.json().get("voices", [])
            if voices_list:
                voice_id = voices_list[-1].get("id") or voices_list[-1].get("voice_id") or ""
                logger.info("voice_id resolved from /v1/voices/custom: %s", voice_id)
        except Exception as _e:
            logger.warning("Fallback voice_id lookup failed: %s", _e)
    if not voice_id:
        raise HTTPException(status_code=502, detail=f"CosyVoice 未返回 voice_id，原始响应: {resp.text[:300]}")

    # ── 步骤 2：E2E 验证 — 立即合成一句短文本确认音色可用 ──────────────────
    verify_text = _VERIFY_TEXT.get(language, _VERIFY_TEXT["zh"])
    try:
        tts = get_tts_provider()
        req = SynthesisRequest(
            text=verify_text,
            voice_id=voice_id,
            language=language,
            response_format="wav",
        )
        result = tts.synthesize(req)
        verified = result.success and bool(result.audio_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"E2E verification failed for voice_id={voice_id}: {exc}")
        verified = False

    if not verified:
        return VoiceCreateResponse(
            voice_id=voice_id,
            name=name,
            verified=False,
            message=(
                "音色注册成功但合成验证失败，参考音频质量不足。"
                "建议：单人朗读、清晰无噪音、10-30 秒、无背景音乐"
            ),
        )

    # ── 步骤 3：写 DB ──────────────────────────────────────────────────────
    existing = db.query(VoiceCatalog).filter_by(voice_id=voice_id).first()
    if existing:
        existing.is_deleted = False
        existing.name = name
        existing.language = language
        existing.gender = gender
        existing.created_by = current_user.user_id
    else:
        db.add(VoiceCatalog(
            voice_id=voice_id,
            name=name,
            language=language,
            gender=gender,
            created_by=current_user.user_id,
        ))
    db.commit()
    logger.info(f"Voice registered: voice_id={voice_id} name={name} by user={current_user.user_id}")

    return VoiceCreateResponse(
        voice_id=voice_id,
        name=name,
        verified=True,
        message="注册并验证成功",
    )


@router.patch("/{voice_id}", response_model=VoiceOut)
def rename_voice(
    voice_id: str,
    name: str = Query(..., description="新音色名称"),
    current_user: CurrentUser = ...,
    db: DbSession = ...,
) -> VoiceOut:
    """修改音色名称（仅创建者可操作）。"""
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="音色名称不能为空")
    voice = db.query(VoiceCatalog).filter_by(voice_id=voice_id, is_deleted=False).first()
    if not voice:
        raise HTTPException(status_code=404, detail="音色不存在")
    if voice.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="只能修改自己注册的音色")
    voice.name = name
    db.commit()
    db.refresh(voice)
    logger.info(f"Voice renamed: voice_id={voice_id} new_name={name} by user={current_user.user_id}")
    return voice


@router.delete("/{voice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voice(
    voice_id: str,
    delete_remote: bool = Query(False, description="是否同步删除 CosyVoice 服务端音色"),
    current_user: CurrentUser = ...,
    db: DbSession = ...,
) -> None:
    """删除音色（仅创建者可操作）。"""
    voice = db.query(VoiceCatalog).filter_by(voice_id=voice_id, is_deleted=False).first()
    if not voice:
        raise HTTPException(status_code=404, detail="音色不存在")
    if voice.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="只能删除自己注册的音色")

    if delete_remote:
        # 调 CosyVoice 删除，失败只记 warning，不阻断本地删除
        try:
            import httpx
            from app.core.config import get_settings
            base_url = get_settings().COSYVOICE_BASE_URL.rstrip("/")
            httpx.delete(f"{base_url}/v1/voices/{voice_id}", timeout=10)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"CosyVoice 远端删除失败（本地仍删除）: {exc}")

    voice.is_deleted = True
    db.commit()
    logger.info(f"Voice deleted: voice_id={voice_id} by user={current_user.user_id}")
