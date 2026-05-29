"""管理类 API：诊断、缓存重载等。

权限：当前 PRD 不区分角色（§4.2），所有登录用户都能调；
后续二期加 admin role 时只需替换 dependency。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.services import few_shot

router = APIRouter()


@router.get("/few-shot/stats")
def few_shot_stats(current_user: CurrentUser) -> dict:
    """Few-shot 索引概览：总数 / 分数分布 / 按语言/按主题分组。"""
    return few_shot.stats()


@router.post("/few-shot/reload")
def few_shot_reload(current_user: CurrentUser) -> dict:
    """清缓存重新扫目录，加完新样本时调一次（无需重启服务）。"""
    result = few_shot.reload_index()
    return {"reloaded": True, **result}
