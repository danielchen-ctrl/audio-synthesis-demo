"""
webapp/task_runner.py
=====================
异步任务队列。
- 提交任务后立即返回 task_id，后台协程处理生成 + 合成。
- 状态流转：queued → generating_text → synthesizing → completed / failed
- 调用现有 embedded_server_main 函数，不复制任何生成逻辑。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import src.webapp.db as db

logger = logging.getLogger(__name__)


# ── runtime.yaml 加载（懒加载，缓存首次结果） ──────────────────────────────────

_runtime_cfg_cache: dict | None = None


def _load_runtime_cfg() -> dict:
    global _runtime_cfg_cache
    if _runtime_cfg_cache is not None:
        return _runtime_cfg_cache
    try:
        import yaml
        cfg_path = ROOT / "config" / "runtime.yaml"
        if cfg_path.exists():
            _runtime_cfg_cache = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        else:
            _runtime_cfg_cache = {}
    except Exception as exc:
        logger.warning("[task_runner] 无法读取 runtime.yaml: %s", exc)
        _runtime_cfg_cache = {}
    return _runtime_cfg_cache

_task_queue: asyncio.Queue = asyncio.Queue()


# ── 辅助 ──────────────────────────────────────────────────────────────────────

def _parse_lines(dialogue_text: str) -> list[tuple[str, str]]:
    """把 'Speaker N: text' 格式文本解析为 (speaker, text) 列表。"""
    lines = []
    for raw in dialogue_text.strip().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        if ": " in raw:
            speaker, text = raw.split(": ", 1)
            lines.append((speaker.strip(), text.strip()))
    return lines


def _guess_scene(template: str, topic: str = "") -> str:
    """从模板标签和/或主题文本推断场景分类。
    两个来源都会检查，任意匹配即返回，覆盖全部 25 个预置主题。"""
    # 合并 template 和 topic，同时检查
    t = ((template or "") + " " + (topic or "")).lower()
    # 医疗健康 — 慢病随访、化疗、手术、护理……
    if any(k in t for k in ["医疗", "健康", "随访", "慢病", "问诊", "化疗", "癌症",
                             "手术", "护理", "诊断", "病历", "患者", "medical", "health"]):
        return "medical"
    # 会议/战略/周会
    if any(k in t for k in ["会议", "周会", "战略", "复盘", "meeting"]):
        return "meeting"
    # 访谈/招聘/人力
    if any(k in t for k in ["访谈", "招聘", "面试", "人力", "补岗", "hr", "interview"]):
        return "interview"
    # 法律/合规
    if any(k in t for k in ["法律", "合规", "法顾", "广告合规", "合同", "审查", "legal"]):
        return "legal"
    # 金融/投资/保险/质检/洞察
    if any(k in t for k in ["金融", "投资", "资产", "保险", "质检", "洞察",
                             "理财", "基金", "证券", "finance"]):
        return "finance"
    # 科技/测试/支付/AI — 测试开发全部 5 个预置主题
    if any(k in t for k in ["科技", "测试", "支付", "人工智能", "付费", "对账",
                             "退款", "稳定性", "准入", "社交", "朋友圈", "隐私",
                             "权限", "分发", "接入", "交易", "tech", "ai"]):
        return "tech"
    # 零售/销售/复购
    if any(k in t for k in ["零售", "会员", "销售", "复购", "retail"]):
        return "sales"
    # 建筑/房地产/工程
    if any(k in t for k in ["房地产", "建筑", "工程", "项目交付", "项目去化",
                             "施工", "楼盘", "去化", "construction"]):
        return "construction"
    # 咨询/专业服务/客户拓展
    if any(k in t for k in ["咨询", "客户拓展", "拓展", "专业服务", "consulting"]):
        return "consulting"
    # 媒体/娱乐/艺人
    if any(k in t for k in ["媒体", "娱乐", "艺人", "商业化", "内容平台", "media"]):
        return "media"
    # 制造业/产线
    if any(k in t for k in ["制造", "产线", "产能", "设备", "生产线", "manufacturing"]):
        return "manufacturing"
    # 汽车/车型投放
    if any(k in t for k in ["汽车", "车型", "投放", "经销商", "试驾", "auto"]):
        return "auto"
    return "other"


def _safe_basename(topic: str) -> str:
    """生成文件名基础部分：主题slug + 当前时间戳（精确到秒）。"""
    slug = re.sub(r"[^\w一-龥\-]", "_", (topic or "")[:40]).strip("_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{slug}_{ts}" if slug else ts


# ── 真人 TTS 合成辅助函数 ──────────────────────────────────────────────────────

async def _fallback_edge_tts(req: Any, output_path: Path) -> Any:
    """
    用 edge_tts 合成一个 SynthesisRequest，作为 real_human 降级路径。
    output_path 应以 .mp3 结尾（edge_tts 原生输出格式）。
    合成后统一重编码为 44100Hz mono，确保与 real_human 片段格式一致，
    避免 concat 拼接处出现采样率/声道差异导致的噪音。
    返回 SynthesisResult（来自 demo_app.tts_provider）。
    """
    import subprocess
    import time
    from demo_app.tts_provider import SynthesisResult
    from demo_app.voice_resolver import EDGE_DEFAULT_VOICES
    from demo_app.embedded_server_main import _ffmpeg_path

    t0 = time.monotonic()
    text = "".join(req.segments)
    # 使用语言默认 edge_tts 音色（不使用 real_human voice_id）
    voice_id = EDGE_DEFAULT_VOICES.get(req.voice_spec.language, "zh-CN-XiaoxiaoNeural")

    try:
        import edge_tts
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # edge_tts 原生输出为 24kHz stereo MP3（因平台而异）
        # 使用 parent/stem 拼接避免 with_suffix(".raw.mp3") 在 Python 3.12+ 因多点后缀报 ValueError
        raw_path = output_path.parent / f"{output_path.stem}.raw.mp3"
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(str(raw_path))

        # 统一重编码为 44100Hz mono，与 real_human 片段格式一致
        # 避免 filter_complex 遇到不同采样率时产生拼接噪音
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    [_ffmpeg_path(), "-y", "-i", str(raw_path),
                     "-c:a", "libmp3lame", "-q:a", "3",
                     "-ar", "44100", "-ac", "1",
                     str(output_path)],
                    check=True, capture_output=True,
                ),
            )
            raw_path.unlink(missing_ok=True)
        except Exception as enc_exc:
            # 重编码失败时回退到原始文件（不完美但好过没有音频）
            logger.warning("[task_runner] edge_tts 重编码失败，使用原始 MP3: %s", enc_exc)
            # replace() 在 Windows 上可安全覆盖已存在的目标文件（rename 不行）
            raw_path.replace(output_path)

        ms = int((time.monotonic() - t0) * 1000)
        return SynthesisResult(
            request=req,
            audio_path=output_path,
            provider_used="edge_tts",
            degraded=True,              # 相对于期望的 real_human 来说是降级
            degraded_reason="real_human_fallback",
            latency_ms=ms,
            api_response_code=None,
            request_chars=len(text),
            audio_duration_ms=0,
            timeline_source="estimated",
        )
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        logger.warning("[task_runner] edge_tts 降级合成也失败: speaker=%s err=%s", req.speaker, exc)
        return SynthesisResult(
            request=req,
            audio_path=None,
            provider_used="edge_tts",
            degraded=True,
            degraded_reason="provider_error",
            latency_ms=ms,
            api_response_code=None,
            request_chars=len(text),
            audio_duration_ms=0,
            timeline_source="original",
        )


async def _concat_audio_segments(seg_files: list[Path], output_path: Path) -> None:
    """
    用 ffmpeg filter_complex concat 将多个音频片段拼接为单个文件。
    与 concat demuxer（-f concat）相比，filter_complex 将所有输入先解码为 PCM
    再拼接重编码，对输入格式/采样率差异完全兼容，不会在拼接点产生爆音或跳帧。
    输出格式由 output_path 后缀决定（.mp3 / .wav）。
    """
    import subprocess
    from demo_app.embedded_server_main import _ffmpeg_path

    # 过滤不存在的片段（降级失败时可能为 None）
    valid = [f for f in seg_files if f and f.exists() and f.stat().st_size > 0]
    if not valid:
        raise RuntimeError("没有有效的音频片段可供拼接")

    ffmpeg = _ffmpeg_path()
    codec = "libmp3lame" if output_path.suffix == ".mp3" else "pcm_s16le"

    if len(valid) == 1:
        # 单片段：直接 transcode，统一格式（用 run_in_executor 避免阻塞事件循环）
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                [ffmpeg, "-y", "-i", str(valid[0]),
                 "-c:a", codec, "-ar", "44100", "-ac", "1",
                 str(output_path)],
                check=True, capture_output=True,
            ),
        )
        return

    # 多片段：使用 filter_complex concat
    # 构建 -i 参数列表
    input_args: list[str] = []
    for f in valid:
        input_args += ["-i", str(f)]

    n = len(valid)
    # filter_complex: [0:a][1:a]...[n-1:a]concat=n=N:v=0:a=1[aout]
    filter_str = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[aout]"

    cmd = (
        [ffmpeg, "-y"]
        + input_args
        + [
            "-filter_complex", filter_str,
            "-map", "[aout]",
            "-c:a", codec,
            "-ar", "44100",   # 统一输出采样率
            "-ac", "1",       # 统一单声道
            str(output_path),
        ]
    )

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: subprocess.run(cmd, check=True, capture_output=True),
    )


async def _convert_wav_to_mp3(wav_path: Path, mp3_path: Path) -> bool:
    """
    将 WAV 文件转换为 MP3（统一格式，避免 ffmpeg concat 混合 WAV/MP3 时的噪音）。
    成功后删除原 WAV，返回 True；失败时保留 WAV，返回 False。
    """
    import subprocess
    from demo_app.embedded_server_main import _ffmpeg_path
    try:
        loop = asyncio.get_running_loop()
        # silenceremove 使用极保守阈值（-65dB）：
        # - CosyVoice 在每段语音前后可能有数秒数字静音（~-90dB 或更低）
        # - -65dB 仅裁掉真正的数字静音，不影响正常语音（语音一般 > -40dB）
        # - start_duration=0.05: 至少 50ms 静音才裁，避免误裁爆破音起始
        # - stop_duration=0.15: 尾部至少 150ms 静音才裁，留自然尾音
        # 注意：曾用 -40dB 阈值，实测中文/英文被裁至仅剩 3~9s，已放弃；-65dB 经测安全。
        silence_filter = (
            "silenceremove="
            "start_periods=1:start_duration=0.05:start_threshold=-65dB:"
            "stop_periods=1:stop_duration=0.15:stop_threshold=-65dB"
        )
        await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                [_ffmpeg_path(), "-y", "-i", str(wav_path),
                 "-af", silence_filter,
                 "-c:a", "libmp3lame", "-q:a", "3",
                 "-ar", "44100", "-ac", "1",   # 统一采样率/声道，避免 concat 拼接噪音
                 str(mp3_path)],
                check=True, capture_output=True,
            ),
        )
        wav_path.unlink(missing_ok=True)
        return True
    except Exception as exc:
        logger.warning("[task_runner] WAV→MP3 转换失败 %s: %s", wav_path.name, exc)
        return False


async def _synthesize_one_segment(
    idx: int,
    req: Any,
    provider: Any,
    save_dir: Path,
    semaphore: asyncio.Semaphore,
    max_retries: int = 0,
) -> tuple:
    """
    并发工作单元：合成单个段落，带 Semaphore 限流。
    - real_human 超时时最多重试 max_retries 次（来自 runtime.yaml tts.real_human.max_retries）
    - real_human 成功后将 WAV 转为 MP3，保证 ffmpeg concat 格式一致（消除噪音）
    - 返回 (idx, result, seg_file, rh_failure_reason, rh_error_msg)
    所有异常均在内部消化，不向外抛出。
    """
    seg_wav = save_dir / f"_seg_{idx:04d}.wav"
    seg_mp3 = save_dir / f"_seg_{idx:04d}.mp3"
    rh_failure_reason: str | None = None
    rh_error_msg: str | None = None
    seg_file: Path | None = None

    async with semaphore:
        try:
            if provider and req.voice_spec.provider == "real_human":
                # ── 首次合成 ────────────────────────────────────────────────────
                result = await provider.synthesize(req, seg_wav)

                # ── 超时重试（最多 max_retries 次）──────────────────────────────
                retries_left = max_retries
                while result.degraded and result.degraded_reason == "timeout" and retries_left > 0:
                    retries_left -= 1
                    logger.info(
                        "[task_runner] real_human 超时，重试 seg=%d（剩余 %d 次）",
                        idx, retries_left,
                    )
                    seg_wav_retry = save_dir / f"_seg_{idx:04d}_r{max_retries - retries_left}.wav"
                    retry_result = await provider.synthesize(req, seg_wav_retry)
                    if not retry_result.degraded:
                        result = retry_result
                        seg_wav = seg_wav_retry   # 改用重试成功的文件
                    else:
                        seg_wav_retry.unlink(missing_ok=True)

                if result.degraded:
                    # 最终仍失败 → 记录原始失败原因，降级到 edge_tts
                    rh_failure_reason = result.degraded_reason or "unknown"
                    rh_error_msg = result.error_msg
                    logger.warning(
                        "[task_runner] real_human 降级 seg=%d speaker=%s reason=%s",
                        idx, req.speaker, rh_failure_reason,
                    )
                    result = await _fallback_edge_tts(req, seg_mp3)
                    seg_file = seg_mp3 if (result.audio_path and result.audio_path.exists()) else None
                else:
                    # real_human 成功 → WAV→MP3 统一格式，消除拼接噪音
                    ok = await _convert_wav_to_mp3(seg_wav, seg_mp3)
                    if ok:
                        seg_file = seg_mp3
                    else:
                        # WAV→MP3 转换失败 → 降级 edge_tts。
                        # 不能将 WAV 直接送入 concat demuxer：ffmpeg concat demuxer
                        # 要求所有输入流 codec 相同，WAV(pcm)/MP3 混合会导致逐字播放或噪音。
                        logger.warning(
                            "[task_runner] WAV→MP3 转换失败 seg=%d，降级 edge_tts 保证格式一致",
                            idx,
                        )
                        seg_wav.unlink(missing_ok=True)
                        result = await _fallback_edge_tts(req, seg_mp3)
                        seg_file = seg_mp3 if (result.audio_path and result.audio_path.exists()) else None
                        if rh_failure_reason is None:
                            rh_failure_reason = "wav_to_mp3_failed"
                            rh_error_msg = "WAV→MP3 conversion failed; fell back to edge_tts"
            else:
                # 直接走 edge_tts（语言无真人音色 or provider 未配置）
                result = await _fallback_edge_tts(req, seg_mp3)
                seg_file = seg_mp3 if (result.audio_path and result.audio_path.exists()) else None
        except Exception as exc:
            logger.error("[task_runner] seg=%d 合成异常: %s", idx, exc)
            from demo_app.tts_provider import SynthesisResult
            result = SynthesisResult(
                request=req, audio_path=None, provider_used="edge_tts",
                degraded=True, degraded_reason="provider_error",
                latency_ms=0, api_response_code=None,
                request_chars=len("".join(req.segments)),
                audio_duration_ms=0, timeline_source="original",
                error_msg=str(exc)[:300],
            )
            rh_failure_reason = "provider_error"
            rh_error_msg = str(exc)[:300]

    return idx, result, seg_file, rh_failure_reason, rh_error_msg


async def _synthesize_with_real_human(
    line_tuples: list[tuple[str, str]],
    language: str,
    save_dir: Path,
    basename: str,
    task: dict,
    output_format: str = "mp3",
) -> dict:
    """
    使用 RealHumanProvider (CosyVoice) 并发合成所有段落。
    - asyncio.gather 并发，Semaphore 限流（默认 5 路）
    - 每段独立合成，失败时自动降级到 edge_tts
    - 返回与 _synthesize_audio_from_lines 兼容的结果字典（含 tts_meta）
    """
    from demo_app.voice_resolver import build_synthesis_requests
    from demo_app.real_human_tts import load_real_human_provider

    # ── 解析 voice_assignments / voice_map ───────────────────────────────────
    voice_assignments: dict = {}
    va_raw = task.get("voice_assignments") or "{}"
    if isinstance(va_raw, str):
        try:
            voice_assignments = json.loads(va_raw)
        except Exception:
            pass
    elif isinstance(va_raw, dict):
        voice_assignments = va_raw

    voice_map: dict = {}
    vm_raw = task.get("voice_map") or "{}"
    if isinstance(vm_raw, str):
        try:
            voice_map = json.loads(vm_raw)
        except Exception:
            pass

    # ── 加载 Provider ─────────────────────────────────────────────────────────
    provider = load_real_human_provider(_load_runtime_cfg())
    effective_provider = "real_human" if provider else "edge_tts"

    if not provider:
        logger.warning(
            "[task_runner] RealHumanProvider 未配置（REAL_HUMAN_TTS_API_URL 未设置），"
            "降级到全量 edge_tts"
        )

    # ── 并发度 & 重试配置 ─────────────────────────────────────────────────────
    rh_cfg = _load_runtime_cfg().get("tts", {}).get("real_human", {})
    max_concurrency = int(rh_cfg.get("max_concurrency", 1))
    max_retries = int(rh_cfg.get("max_retries", 0))
    # max_chars_per_segment：同说话人连续行合并上限。
    # CosyVoice 为单 GPU 队列，总吞吐恒定 ~6 cps，并发无法加速。
    # 较小值 → 段落更短、每段更快完成、进度更新更频繁（但总时间不变）。
    # 较大值 → 更少 HTTP 往返，单段效率略高（测量约 4.2x realtime@500chars vs 1.2x@12chars）。
    # 推荐：中文对话 200–500，英文对话 400–800。
    max_chars = int(rh_cfg.get("max_chars_per_segment", 500))
    semaphore = asyncio.Semaphore(max_concurrency)

    # ── 构建 SynthesisRequest 列表（段落合并） ────────────────────────────────
    synthesis_requests = build_synthesis_requests(
        line_tuples,
        language=language,
        voice_assignments=voice_assignments,
        voice_map=voice_map,
        effective_provider=effective_provider,
        max_chars=max_chars,
    )

    # ── 并发合成所有段落 ──────────────────────────────────────────────────────
    tasks = [
        _synthesize_one_segment(idx, req, provider, save_dir, semaphore, max_retries)
        for idx, req in enumerate(synthesis_requests)
    ]
    raw_results = await asyncio.gather(*tasks)

    # 按原始顺序排列（gather 顺序已确定，但防御性排序）
    raw_results = sorted(raw_results, key=lambda r: r[0])

    # ── 组装结果列表 ──────────────────────────────────────────────────────────
    seg_files: list[Path | None] = []
    tts_meta: list[dict] = []
    fallback_reasons: list[str] = []

    for idx, result, seg_file, rh_failure_reason, rh_error_msg in raw_results:
        seg_files.append(seg_file)
        if rh_failure_reason:
            fallback_reasons.append(f"seg{idx}:{rh_failure_reason}")

        req = synthesis_requests[idx]
        # 查 voice_name：从 COSYVOICE_VOICE_CATALOG 按 voice_id 反查名称
        _vid = req.voice_spec.voice_id if req.voice_spec else ""
        _vname = ""
        if _vid:
            from demo_app.voice_resolver import COSYVOICE_VOICE_CATALOG
            for _lang_voices in COSYVOICE_VOICE_CATALOG.values():
                for _v in _lang_voices:
                    if _v.get("voice_id") == _vid:
                        _vname = _v.get("name", "")
                        break
                if _vname:
                    break
            if not _vname:
                _vname = _vid  # 找不到名称时显示 voice_id 本身
        tts_meta.append({
            "segment_idx": idx,
            "speaker": req.speaker,
            "voice_id": _vid,
            "voice_name": _vname,
            "provider_used": result.provider_used if result else "edge_tts",
            "degraded": (rh_failure_reason is not None) or (result.degraded if result else True),
            "degraded_reason": rh_failure_reason or (result.degraded_reason if result else "no_provider"),
            "error_msg": rh_error_msg if rh_failure_reason else None,
            "latency_ms": result.latency_ms if result else 0,
            "chars": result.request_chars if result else 0,
            "job_id": result.job_id if result else None,
            "poll_count": result.poll_count if result else None,
        })

    # ── 拼接所有片段 ─────────────────────────────────────────────────────────
    final_ext = f".{output_format}"
    final_path = save_dir / f"{basename}{final_ext}"
    valid_segs = [f for f in seg_files if f]

    try:
        await _concat_audio_segments(valid_segs, final_path)
    finally:
        # 清理临时片段文件
        for f in seg_files:
            if f:
                try:
                    f.unlink()
                except Exception:
                    pass

    # ── 构造返回值 ────────────────────────────────────────────────────────────
    warn = ""
    if fallback_reasons:
        warn = "real_human_partial_fallback:" + ",".join(fallback_reasons)
    elif not provider:
        warn = "real_human_unavailable:all_edge_tts"

    return {
        "audio_file_path": str(final_path),
        "output_format": output_format,
        "warning": warn,
        "tts_meta": json.dumps(tts_meta, ensure_ascii=False),
        "segments_json_path": None,
        "transcript_srt_path": None,
    }


# ── 核心处理逻辑 ──────────────────────────────────────────────────────────────

async def _process_task(task_id: str) -> None:
    task = db.get_task(task_id)
    if not task:
        logger.warning("Task %s not found in DB", task_id)
        return

    # 导入生成函数（懒加载，避免启动时加载 bundle）
    try:
        from demo_app.embedded_server_main import (
            _generate_text_payload,
            _synthesize_audio_from_lines,
            load_bundle_server,
        )
    except ImportError as exc:
        logger.error("Failed to import generation modules: %s", exc)
        db.update_task_status(task_id, "failed", error_msg=f"模块加载失败: {exc}")
        return

    generation_mode = task.get("generation_mode", "llm")
    language = task.get("language", "中文")
    topic = task.get("topic") or ""
    people_count = int(task.get("people_count") or 2)
    word_count = int(task.get("word_count") or 1000)
    output_format = task.get("output_format") or "mp3"
    include_scripts = bool(task.get("include_scripts", 0))
    voice_map: dict[str, str] = json.loads(task.get("voice_map") or "{}")
    dialogue_id: str | None = None
    text_path_from_payload: str | None = None
    basename_from_payload: str | None = None

    # ── Step 1: 生成文本 ───────────────────────────────────────────────────
    db.update_task_status(task_id, "generating_text")
    logger.info("Task %s: generating text (mode=%s)", task_id, generation_mode)

    try:
        if generation_mode == "direct":
            input_text = task.get("input_text") or ""
            line_tuples = _parse_lines(input_text)
            if not line_tuples:
                raise ValueError("直接输入文本格式错误，无法解析对话行")
        else:
            payload: dict[str, Any] = {
                "title": topic,
                "scenario": topic,
                "core_content": task.get("custom_prompt") or topic,
                "people_count": people_count,
                "word_count": word_count,
                "language": language,
                "audio_language": language,
                "template_label": task.get("template") or "",
                "keyword_terms": json.loads(task.get("keywords") or "[]"),
            }
            bundle_server = load_bundle_server()
            task_save_dir = ROOT / "storage" / "generated" / task_id
            loop = asyncio.get_running_loop()
            result: dict = await loop.run_in_executor(
                None,
                lambda: _generate_text_payload(
                    bundle_server, payload, save_dir=task_save_dir
                ),
            )
            if not result.get("ok"):
                raise RuntimeError(result.get("error") or "文本生成失败（未知错误）")
            dialogue_id = result["dialogue_id"]
            text_path_from_payload = result.get("text_path")
            basename_from_payload = result.get("basename")
            line_tuples = _parse_lines(result["dialogue_text"])
            if not line_tuples:
                raise RuntimeError("LLM 返回文本为空或格式错误")

    except Exception as exc:
        logger.exception("Task %s text generation failed", task_id)
        db.update_task_status(task_id, "failed", error_msg=str(exc))
        return

    # ── Step 1.5: 仅文本模式 — 跳过音频合成，直接保存 txt 文件 ──────────────
    if generation_mode == "text_only":
        save_dir = ROOT / "storage" / "generated" / task_id
        save_dir.mkdir(parents=True, exist_ok=True)
        if text_path_from_payload:
            # LLM 分支：_generate_text_payload 已写好 txt（含 bundle 标准渲染 + manifest），直接复用
            txt_path = Path(text_path_from_payload)
        else:
            # direct 输入兜底：自己写一份
            basename = _safe_basename(topic)
            txt_path = save_dir / f"{basename}.txt"
            text_content = "\n".join(f"{spk}: {txt}" for spk, txt in line_tuples)
            txt_path.write_text(text_content, encoding="utf-8")
        file_size = txt_path.stat().st_size

        tx_json: str | None = json.dumps(
            [{"speaker": spk, "text": txt, "start_time": None, "end_time": None}
             for spk, txt in line_tuples],
            ensure_ascii=False,
        ) if line_tuples else None

        file_record = db.create_audio_file({
            "task_id": task_id,
            "file_name": txt_path.name,
            "file_path": str(txt_path),
            "source": "generated",
            "duration": 0.0,
            "format": "txt",
            "file_size": file_size,
            "language": language,
            "speaker_count": people_count,
            "scene": _guess_scene(task.get("template") or "", topic),
            "topic": topic,
            "transcript_json": tx_json,
        })
        db.update_task_status(
            task_id,
            "completed",
            file_id=file_record["file_id"],
            dialogue_id=dialogue_id or "",
        )
        logger.info("Task %s (text_only) completed → file_id=%s", task_id, file_record["file_id"])
        return

    # ── Step 2: 合成音频 ───────────────────────────────────────────────────
    db.update_task_status(task_id, "synthesizing")
    logger.info("Task %s: synthesizing audio (%d lines)", task_id, len(line_tuples))

    # direct 模式：若前端传来了 dialogue_id（文本已写入该目录），
    # 优先用 dialogue_id 目录，保证 txt + manifest + 音频落在同一文件夹。
    # llm 模式：_generate_text_payload 已写到 task_id 目录，继续用 task_id。
    _pre_dialogue_id = dialogue_id or task.get("dialogue_id") or ""
    _pre_dir = ROOT / "storage" / "generated" / _pre_dialogue_id if _pre_dialogue_id else None
    if _pre_dir and _pre_dir.exists() and generation_mode == "direct":
        save_dir = _pre_dir
    else:
        save_dir = ROOT / "storage" / "generated" / task_id
    save_dir.mkdir(parents=True, exist_ok=True)
    # 优先复用 _generate_text_payload 写 txt/manifest 时的 basename，
    # 保证同一 task 目录下 txt 与音频文件名一致（direct 模式没有 payload 时兜底）
    basename = basename_from_payload or _safe_basename(topic)

    tts_provider = task.get("tts_provider") or "edge_tts"

    try:
        if tts_provider == "real_human":
            audio_result: dict = await _synthesize_with_real_human(
                line_tuples, language, save_dir, basename, task,
                output_format=output_format,
            )
        else:
            bundle_server = load_bundle_server()
            audio_result = await _synthesize_audio_from_lines(
                line_tuples,
                language,
                save_dir,
                basename,
                bundle_server,
                selected_voice_map=voice_map or None,
                output_format=output_format,
                include_scripts=include_scripts,
            )
    except Exception as exc:
        logger.exception("Task %s synthesis failed", task_id)
        db.update_task_status(task_id, "failed", error_msg=str(exc))
        return

    # ── Step 3: 落库 ──────────────────────────────────────────────────────
    audio_path = Path(audio_result["audio_file_path"])
    file_size = audio_path.stat().st_size if audio_path.exists() else 0

    # 从 segments JSON 读取时长（仅当 include_scripts=True 时有值）
    duration = 0.0
    segs_path = audio_result.get("segments_json_path") or ""
    if segs_path and Path(segs_path).exists():
        try:
            segs = json.loads(Path(segs_path).read_text(encoding="utf-8"))
            if segs and isinstance(segs, list):
                duration = float(segs[-1].get("end_time", 0))
        except Exception:
            pass

    # 若 segments 不可用，直接读取音频文件时长（ffprobe 探针，零内存）
    if duration == 0.0 and audio_path.exists():
        try:
            from demo_app.embedded_server_main import _probe_duration_secs
            duration = _probe_duration_secs(audio_path)
        except Exception:
            pass

    # ── transcript_json ──────────────────────────────────────────────────
    # 优先使用带时间戳的 segments JSON（include_scripts=True 时产生）
    # 否则用对话行列表构造无时间戳的基础台本，保证详情页始终能显示文本
    transcript_json: str | None = None
    if segs_path and Path(segs_path).exists():
        transcript_json = Path(segs_path).read_text(encoding="utf-8")
    if not transcript_json and line_tuples:
        transcript_json = json.dumps(
            [{"speaker": spk, "text": txt, "start_time": None, "end_time": None}
             for spk, txt in line_tuples],
            ensure_ascii=False,
        )

    transcript_srt: str | None = None
    srt_path = audio_result.get("transcript_srt_path") or ""
    if srt_path and Path(srt_path).exists():
        transcript_srt = Path(srt_path).read_text(encoding="utf-8")

    file_record = db.create_audio_file(
        {
            "task_id": task_id,
            "file_name": audio_path.name,
            "file_path": str(audio_path),
            "source": "generated",
            "duration": duration,
            "format": audio_result.get("output_format", output_format),
            "file_size": file_size,
            "language": language,
            "speaker_count": people_count,
            "scene": _guess_scene(task.get("template") or "", topic),
            "topic": topic,
            "transcript_json": transcript_json,
            "transcript_srt": transcript_srt,
            "tts_meta": audio_result.get("tts_meta"),   # 真人 TTS 逐段详情（可能为 None）
        }
    )

    tts_warn = (audio_result.get("warning") or "").strip()
    db.update_task_status(
        task_id,
        "completed",
        file_id=file_record["file_id"],
        dialogue_id=dialogue_id or "",
        error_msg=f"[TTS_WARN] {tts_warn}" if tts_warn else None,
    )
    logger.info("Task %s completed → file_id=%s (tts_warn=%s)", task_id, file_record["file_id"], bool(tts_warn))


# ── 后台 worker ───────────────────────────────────────────────────────────────

async def _worker() -> None:
    logger.info("[platform] Task worker started")
    while True:
        task_id: str = await _task_queue.get()
        try:
            await _process_task(task_id)
        except Exception:
            logger.exception("Unhandled error in task worker for task %s", task_id)
        finally:
            _task_queue.task_done()


def enqueue(task_id: str) -> None:
    """将 task_id 加入处理队列（从 Tornado handler 同步调用安全）。"""
    loop = asyncio.get_running_loop()
    loop.call_soon_threadsafe(_task_queue.put_nowait, task_id)


_MAX_WORKERS = 3  # 与 handlers.py 中的并发限制（count_active_tasks >= 3）保持一致


def _recover_stuck_tasks() -> int:
    """将上次服务崩溃时卡在中间状态（generating_text / synthesizing）的任务重置为 queued。
    updated_at 超过 10 分钟的才重置，避免误重置当前正在处理的任务。"""
    try:
        import sqlite3
        from pathlib import Path as _P
        _db_path = _P(__file__).resolve().parents[2] / "runtime" / "platform.db"
        if not _db_path.exists():
            return 0
        conn = sqlite3.connect(str(_db_path), check_same_thread=False)
        result = conn.execute(
            """UPDATE tasks SET status='queued', error_msg=NULL
               WHERE status IN ('generating_text','synthesizing')
               AND updated_at < datetime('now','-10 minutes')"""
        )
        count = result.rowcount
        conn.commit()
        conn.close()
        if count:
            logger.info("[task-recovery] Reset %d stuck task(s) → queued", count)
        return count
    except Exception as exc:
        logger.warning("[task-recovery] Failed: %s", exc)
        return 0


def backfill_scenes() -> int:
    """回填存量 audio_files 中 scene='other' 的记录，使用 topic 重新推断分类。
    在 start_worker() 时调用一次，幂等。返回更新条数。"""
    try:
        import sqlite3
        from pathlib import Path as _P
        _db_path = _P(__file__).resolve().parents[2] / "runtime" / "platform.db"
        if not _db_path.exists():
            return 0
        conn = sqlite3.connect(str(_db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT file_id, topic, task_id FROM audio_files WHERE deleted=0 AND scene='other'"
        ).fetchall()
        updated = 0
        for row in rows:
            file_topic = row["topic"] or ""
            task_template = ""
            if row["task_id"]:
                t = conn.execute(
                    "SELECT template, topic FROM tasks WHERE task_id=?", (row["task_id"],)
                ).fetchone()
                if t:
                    task_template = t["template"] or ""
                    if not file_topic:
                        file_topic = t["topic"] or ""
            new_scene = _guess_scene(task_template, file_topic)
            if new_scene != "other":
                conn.execute(
                    "UPDATE audio_files SET scene=? WHERE file_id=?",
                    (new_scene, row["file_id"]),
                )
                updated += 1
        conn.commit()
        conn.close()
        if updated:
            logger.info("[scene-backfill] Updated %d file(s) from 'other' to inferred scenes", updated)
        return updated
    except Exception as exc:
        logger.warning("[scene-backfill] Failed: %s", exc)
        return 0


def start_worker() -> None:
    """在 Tornado IOLoop 启动后调用一次，启动后台 worker 协程（并发数 = _MAX_WORKERS）。"""
    _recover_stuck_tasks()     # 恢复上次崩溃遗留的中间态任务
    backfill_scenes()          # 一次性回填存量 scene='other' 的文件
    for _ in range(_MAX_WORKERS):
        asyncio.ensure_future(_worker())
