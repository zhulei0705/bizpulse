"""T06 实验漏斗与转化指标（全部基于真实数据；分母为企业数，不是互动条数）。

关键规则（任务书三十七/七十一/七十二/七十三节）：
- 漏斗按验证目标企业（ExperimentTarget）计数；一个企业跟进 5 次仍算 1 家；
- 转化率分母为上一漏斗阶段的企业数；分母为 0 时返回 0（不除零，统一设计）；
- contracted_revenue 只来自真实成交（ExperimentOutcome.contract_amount）；
  received_revenue 只来自真实收款（Interaction type=PAYMENT）；报价金额不是收入。
"""
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import TARGET_STATUS_RANK
from app.models.experiment import ExperimentOutcome, ExperimentTarget, Interaction


def _rate(numerator: int, denominator: int) -> float:
    """相邻漏斗转化率；分母为 0 统一返回 0（关键测试 1：不除零）。"""
    if denominator <= 0:
        return 0
    return round(numerator / denominator * 100, 2)


def experiment_funnel(db: Session, experiment_id: str) -> dict:
    """真实验证漏斗（按企业数；状态可回退但 reached_stage 记录到达过的最远阶段）。"""
    targets = db.scalars(select(ExperimentTarget).where(ExperimentTarget.experiment_id == experiment_id)).all()
    ranks = [TARGET_STATUS_RANK.get(t.reached_stage, 0) for t in targets]

    def at_least(stage: str) -> int:
        threshold = TARGET_STATUS_RANK[stage]
        return sum(1 for r in ranks if r >= threshold)

    return {
        "targets": len(targets),
        "researching": at_least("RESEARCHING"),
        "ready_to_contact": at_least("READY_TO_CONTACT"),
        "contacted": at_least("CONTACTED"),
        "replied": at_least("REPLIED"),
        "qualified": at_least("QUALIFIED"),
        "meetings": at_least("MEETING"),
        "quotes": at_least("QUOTED"),
        "pilots": at_least("PILOT"),
        "wins": at_least("WON"),
        "rejected": sum(1 for t in targets if t.status == "REJECTED"),
        "no_response": sum(1 for t in targets if t.status == "NO_RESPONSE"),
        "paused": sum(1 for t in targets if t.status == "PAUSED"),
    }


def experiment_metrics(db: Session, experiment_id: str) -> dict:
    """真实转化指标：相邻漏斗转化率 + 分离的真实收入 + 触达/积极回复（任务书四十八）。"""
    funnel = experiment_funnel(db, experiment_id)

    targets = db.scalars(select(ExperimentTarget).where(ExperimentTarget.experiment_id == experiment_id)).all()
    # Reachable Rate：有真实可用联系人（VERIFIED_PUBLIC/USER_PROVIDED）的目标企业占比
    from app.models.company import CompanyContact
    reachable_ids = {
        c.company_id for c in db.scalars(
            select(CompanyContact).where(CompanyContact.verification_status.in_(["VERIFIED_PUBLIC", "USER_PROVIDED"]))
        ).all()
    }
    reachable_count = sum(1 for t in targets if t.company_id in reachable_ids)

    # Positive Reply Rate：真实回复中人工分类为 POSITIVE 的企业数 / 回复企业数
    positive_company_ids = set(db.scalars(
        select(Interaction.company_id).where(
            Interaction.experiment_id == experiment_id,
            Interaction.interaction_type == "REPLY",
            Interaction.result == "POSITIVE",
        )
    ).all())
    positive_count = sum(1 for t in targets if t.company_id in positive_company_ids)

    outcomes = db.scalars(select(ExperimentOutcome).where(ExperimentOutcome.experiment_id == experiment_id)).all()
    contracted = sum((o.contract_amount or Decimal("0") for o in outcomes if o.won), Decimal("0"))
    # received_revenue 只来自真实收款互动（PAYMENT）；报价/合同金额都不算已收款
    received_rows = db.scalars(
        select(Interaction.revenue).where(
            Interaction.experiment_id == experiment_id,
            Interaction.interaction_type == "PAYMENT",
            Interaction.revenue.is_not(None),
        )
    ).all()
    received = sum((Decimal(str(v)) for v in received_rows), Decimal("0"))

    return {
        **funnel,
        "reachable_count": reachable_count,
        "reachable_rate": _rate(reachable_count, funnel["targets"]),
        "contact_rate": _rate(funnel["contacted"], funnel["targets"]),
        "reply_rate": _rate(funnel["replied"], funnel["contacted"]),
        "positive_reply_rate": _rate(positive_count, funnel["replied"]),
        "meeting_rate": _rate(funnel["meetings"], funnel["replied"]),
        "quote_rate": _rate(funnel["quotes"], funnel["meetings"]),
        "pilot_rate": _rate(funnel["pilots"], funnel["quotes"]),
        "close_rate": _rate(funnel["wins"], funnel["pilots"]),
        "overall_close_rate": _rate(funnel["wins"], funnel["contacted"]),
        "contracted_revenue": float(contracted),
        "received_revenue": float(received),
        # 兼容 T04 时期字段名（revenue = 真实已收款；报价从来不算收入）
        "revenue": float(received),
        "deals": funnel["wins"],
    }


def interaction_metrics(db: Session, experiment_id: str) -> dict:
    """互动层参考数据（不计入转化率，只做辅助视图）。"""
    interactions = db.scalars(select(Interaction).where(Interaction.experiment_id == experiment_id)).all()
    outbound = sum(1 for x in interactions if x.direction == "OUTBOUND")
    inbound = sum(1 for x in interactions if x.direction == "INBOUND")
    replies = sum(1 for x in interactions if x.interaction_type == "REPLY")
    return {
        "interactions_total": len(interactions),
        "interactions_outbound": outbound,
        "interactions_inbound": inbound,
        "interactions_replies": replies,
    }
