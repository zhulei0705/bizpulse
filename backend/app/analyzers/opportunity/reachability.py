"""ReachabilityAnalyzer —— 企业可触达性（T05，T08.2 增强）。

只用真实渠道：官网公开邮箱/电话/官方联系表单（CompanyContact，verified_public）、
Company.website/domain。没有公开渠道则降低分数。禁止生成假邮箱/手机号/联系人。

T08.2 任务书二十/二十一：
- 权重可配置（settings.reachability_weights）：公开商务邮箱 > 官方表单 > 仅总机电话；
- HR/客服等渠道只证明可触达：提高 Reachability，但 is_decision_maker 不随之升级。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.analyzers.opportunity.context import CompanyAnalysisContext

# 渠道权重（默认值；settings.reachability_weights 可覆盖）
DEFAULT_CHANNEL_WEIGHTS: dict[str, int] = {
    "VERIFIED_EMAIL": 80,      # 官网公开商务邮箱
    "VERIFIED_FORM": 65,       # 官方联系表单
    "VERIFIED_PHONE": 55,      # 仅公开电话（总机）
    "UNVERIFIED": 40,
    "WEBSITE_ONLY": 45,
}


def _weights() -> dict[str, int]:
    try:
        from app.core.config import settings

        configured = getattr(settings, "reachability_weights", None)
        if isinstance(configured, dict) and configured:
            return {**DEFAULT_CHANNEL_WEIGHTS, **configured}
    except Exception:  # noqa: BLE001 - 配置缺失用默认权重
        pass
    return DEFAULT_CHANNEL_WEIGHTS


@dataclass
class ReachabilityResult:
    score: int
    reasons: list[str] = field(default_factory=list)


def _channel_of(c) -> str | None:
    if c.email:
        return "EMAIL"
    if c.phone:
        return "PHONE"
    if c.public_profile_url:
        return "WEBSITE_FORM"
    return None


def compute_reachability(ctx: CompanyAnalysisContext) -> ReachabilityResult:
    reasons: list[str] = []
    w = _weights()
    contacts = ctx.contacts

    verified = [c for c in contacts if c.verified_public]
    verified_email = [c for c in verified if _channel_of(c) == "EMAIL"]
    verified_form = [c for c in verified if _channel_of(c) == "WEBSITE_FORM"]
    verified_phone = [c for c in verified if _channel_of(c) == "PHONE"]
    public = [c for c in contacts if not c.verified_public and _channel_of(c)]

    score = 0
    if verified_email:
        score = max(score, min(100, w["VERIFIED_EMAIL"] + 5 * len(verified_email)))
        reasons.append(f"有 {len(verified_email)} 个官网公开邮箱（可直邮触达）")
    if verified_form:
        score = max(score, w["VERIFIED_FORM"])
        reasons.append(f"有 {len(verified_form)} 个官方联系表单（可提交合作意向）")
    if verified_phone:
        phone_only = not verified_email and not verified_form
        phone_score = w["VERIFIED_PHONE"] if phone_only else min(100, w["VERIFIED_PHONE"] + 20)
        score = max(score, phone_score)
        reasons.append(f"有 {len(verified_phone)} 个公开电话（{'仅总机，触达性一般' if phone_only else '辅助渠道'}）")
    if not verified and public:
        score = max(score, w["UNVERIFIED"])
        reasons.append(f"有 {len(public)} 个未验证公开联系方式")

    if ctx.company.website or ctx.company.domain:
        score = max(score, w["WEBSITE_ONLY"])
        reasons.append(f"有公开官网（{ctx.company.website or ctx.company.domain}），可通过官网销售入口触达")
    if ctx.company.main_markets:
        score = max(score, 35)

    if score == 0:
        reasons.append("无公开联系方式且无官网 → 可触达性极低（禁止生成假联系人）")

    return ReachabilityResult(score=max(0, min(score, 100)), reasons=reasons)
