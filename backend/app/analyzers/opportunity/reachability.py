"""ReachabilityAnalyzer —— 企业可触达性（T05）。

只用真实渠道：官网联系方式（CompanyContact.verified_public / public_contact）、
公开商务邮箱、公开销售入口、Company.website/domain。没有公开渠道则降低分数。
禁止生成假邮箱/手机号/联系人。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.analyzers.opportunity.context import CompanyAnalysisContext


@dataclass
class ReachabilityResult:
    score: int
    reasons: list[str] = field(default_factory=list)


def compute_reachability(ctx: CompanyAnalysisContext) -> ReachabilityResult:
    reasons: list[str] = []
    contacts = ctx.contacts
    verified = [c for c in contacts if c.verified_public and (c.public_contact or c.name)]
    public = [c for c in contacts if not c.verified_public and (c.public_contact or c.name)]

    if verified:
        score = min(100, 80 + 5 * len(verified))
        reasons.append(f"有 {len(verified)} 个已验证公开联系方式（官网等公开来源）")
    elif public:
        score = min(100, 60 + 5 * len(public))
        reasons.append(f"有 {len(public)} 个公开联系方式（未人工验证）")
    else:
        score = 0

    if ctx.company.website or ctx.company.domain:
        score = max(score, 45)
        reasons.append(f"有公开官网（{ctx.company.website or ctx.company.domain}），可通过官网销售入口触达")
    if ctx.company.main_markets:
        score = max(score, 35)

    if score == 0:
        reasons.append("无公开联系方式且无官网 → 可触达性极低（禁止生成假联系人）")

    return ReachabilityResult(score=max(0, min(score, 100)), reasons=reasons)
