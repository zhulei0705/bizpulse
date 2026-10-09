"""T08.1 机会可行动性（Actionability）：把"采购事件生命周期"接到商业验证池入口。

核心语义（任务书第六/三十/三十一节）：
- AWARDED（已中标）→ 供应商侧 HISTORICAL_SIGNAL（能力证据）/ 采购方侧 NOT_ACTIONABLE（采购历史）；
- CLOSED / CANCELLED → NOT_ACTIONABLE；
- OPEN（招标未截止）→ ACTIONABLE_NOW；ANNOUNCED（无截止时间）→ WATCH；
- 验证门采用黑名单式：仅明确已结束的采购事件（NOT_ACTIONABLE / HISTORICAL_SIGNAL）
  不得进入 ACTIONABLE 验证池；UNKNOWN（无法判定）不拦截但需人工留意。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.opportunity import Opportunity
from app.models.signal import Signal
from app.services import procurement_parser as pp

# 不得进入 ACTIONABLE 验证池的状态（已结束的采购事件）
BLOCKING_ACTIONABILITY = {"NOT_ACTIONABLE", "HISTORICAL_SIGNAL", "INVALID_EVIDENCE"}

# T08.2 规则优先的 Actionability Analyzer（任务书二十二~二十五）：
# 时间 + 事件状态 + 类型 → 状态；LLM 只允许辅助复杂语义，不独断。

# 当前进行中的行为类信号（招聘 = 企业当前扩张行为；无日期也按当前处理）
_ONGOING_SIGNAL_TYPES = {
    "HIRING", "SALES_HIRING", "AI_HIRING", "CUSTOMER_SERVICE_HIRING", "FINANCE_HIRING",
    "TECH_HIRING", "PROCUREMENT_HIRING", "SUPPLY_CHAIN_HIRING",
    "SUPPLIER_SEARCH", "CRM_DEMAND", "ERP_DEMAND", "AI_DEMAND", "AUTOMATION_DEMAND",
    "DIGITAL_TRANSFORMATION", "AI_TRANSFORMATION",
}
# 事件类信号（近 90 天内发生才 ACTIONABLE_NOW，更早 → WATCH）
_EVENT_SIGNAL_TYPES = {
    "NEW_PRODUCT", "NEW_SERVICE", "NEW_MARKET", "NEW_FACTORY", "NEW_OFFICE",
    "OVERSEAS_EXPANSION", "EXPANSION", "FUNDING", "PARTNERSHIP", "STRATEGIC_COOPERATION",
}
_EVENT_RECENCY_DAYS = 90


def _freshness(signal: Signal, now) -> int | None:
    """仅显式事件/发布时间参与新鲜度；采集时间不证明近期，无时间返回未知。"""
    # published_at 仅网页显式发布时间；采集时间不是事件时间。
    # 已有明确 event_at 优先，不能从正文相邻日期猜。
    event = (getattr(signal, 'payload_json', None) or {}).get('event_at')
    anchor = signal.published_at
    if event:
        from datetime import datetime
        try:anchor = datetime.fromisoformat(event)
        except (ValueError, TypeError):return None
    if anchor is None:
        record = getattr(signal, 'source_record', None)
        meta = getattr(record, 'metadata_json', None) or {}
        date = (meta.get('structured_fields') or {}).get('published_at') or {}
        if date.get('status') == 'EXTRACTED_UNVERIFIED' and date.get('value'):
            from datetime import datetime
            try:anchor = datetime.fromisoformat(date['value'])
            except (ValueError, TypeError):return None
    if anchor is None:
        return None
    if anchor.tzinfo is None:
        from datetime import timezone

        # 无时区仅按公告日历日期估算天数，不虚构 UTC 时刻。
        return (now.date() - anchor.date()).days
    return (now - anchor).days


def compute_actionability_by_rules(signal: Signal, *, now=None) -> str:
    """规则版可行动性（T08.2 新增信号适用；不覆盖已有 t08_audit 审计结果）。"""
    from datetime import datetime, timezone

    now = now or datetime.now(timezone.utc)
    st = signal.signal_type

    if st == "CONTRACT_AWARD":
        # 中标 = 已授予（T08.1 语义：供应商侧历史能力证据）
        role = ((signal.payload_json or {}).get("t08_audit") or {}).get("subject_role") or "SUPPLIER"
        return pp.derive_actionability("AWARDED", role)

    if st in {"PROCUREMENT", "TENDER"}:
        record = signal.source_record
        text = record.raw_text if record is not None else None
        deadline = pp.parse_deadline(text)
        lifecycle = pp.parse_procurement_lifecycle(text, deadline=deadline)
        return pp.derive_actionability(lifecycle, "BUYER")

    if st in _ONGOING_SIGNAL_TYPES:
        days = _freshness(signal, now)
        # 招聘/需求类是"当前行为"；超过 180 天且无新证据则视为过期
        if days is None or days < 0 or days > 180:
            return "WATCH"
        return "ACTIONABLE_NOW"

    if st in _EVENT_SIGNAL_TYPES:
        days = _freshness(signal, now)
        if days is None:
            return "WATCH"
        return "ACTIONABLE_NOW" if 0 <= days <= _EVENT_RECENCY_DAYS else "WATCH"

    # 痛点族/其他：默认 WATCH（需人工确认），不武断
    return "WATCH"


def record_signal_actionability(db: Session, signal: Signal) -> str:
    """计算并把 actionability 写入 signal.payload_json（幂等；已有审计结果时不覆盖）。"""
    payload = dict(signal.payload_json or {})
    explicit = payload.get("actionability") or {}
    status = (
        explicit.get("status")
        or (payload.get("t08_audit") or {}).get("actionability_status")
        or compute_actionability_by_rules(signal)
    )
    if not payload.get("actionability"):
        payload["actionability"] = {
            "status": status,
            "computed_by": "rule_actionability_v1",
        }
        signal.payload_json = payload
        db.flush()
    return status


def compute_signal_actionability(db: Session, signal: Signal) -> str:
    """单条信号的可行动性：审计结果 > 显式 actionability 块 > 规则实时判定（代码规则，不猜）。"""
    if db is not None and hasattr(db, 'get'):
        from app.services.evidence_integrity import signal_issues
        if signal_issues(db, signal):return 'INVALID_EVIDENCE'
    if signal.signal_type == 'CONTRACT_AWARD':
        role = ((signal.payload_json or {}).get('t08_audit') or {}).get('subject_role') or 'SUPPLIER'
        return pp.derive_actionability('AWARDED', role)
    # 旧缓存 ACTIONABLE_NOW 也不能覆盖已知历史/缺失时间。
    if signal.signal_type in _EVENT_SIGNAL_TYPES | _ONGOING_SIGNAL_TYPES:
        safe = compute_actionability_by_rules(signal)
        if safe != 'ACTIONABLE_NOW':return safe
    audit = (signal.payload_json or {}).get("t08_audit") or {}
    if audit.get("actionability_status"):
        return audit["actionability_status"]
    explicit = (signal.payload_json or {}).get("actionability") or {}
    if explicit.get("status"):
        return explicit["status"]

    if signal.signal_type == "CONTRACT_AWARD":
        # 中标公告 → 事件已结束；主体默认供应商侧（发现管线只挂供应商）
        role = audit.get("subject_role") or "SUPPLIER"
        return pp.derive_actionability("AWARDED", role)

    if signal.signal_type in {"PROCUREMENT", "TENDER", "SUPPLIER_SEARCH"}:
        record = signal.source_record
        text = record.raw_text if record is not None else None
        deadline = pp.parse_deadline(text)
        lifecycle = pp.parse_procurement_lifecycle(text, deadline=deadline)
        return pp.derive_actionability(lifecycle, "BUYER")

    # 其余类型走规则版判定（T08.2：T04 生成信号必须经过 Actionability Analyzer）
    return compute_actionability_by_rules(signal)


def opportunity_actionability(db: Session, opportunity: Opportunity) -> dict:
    """机会级可行动性：取主信号判定，附判定依据（供报告与验证门使用）。"""
    from app.services.evidence_integrity import opportunity_issues
    issues = opportunity_issues(db, opportunity)
    if issues:return {'actionability_status': 'INVALID_EVIDENCE', 'basis': issues}
    signal = db.get(Signal, opportunity.primary_signal_id) if opportunity.primary_signal_id else None
    if signal is None:
        return {"actionability_status": "UNKNOWN", "basis": "无主信号"}
    status = compute_signal_actionability(db, signal)
    audit = (signal.payload_json or {}).get("t08_audit") or {}
    basis = {
        "signal_id": signal.id,
        "signal_type": signal.signal_type,
        "procurement_status": audit.get("procurement_status"),
        "subject_role": audit.get("subject_role"),
    }
    return {"actionability_status": status, "basis": basis}


def is_actionable_for_validation(status: str) -> bool:
    """验证门用：黑名单式 —— 只有明确已结束的采购事件才拦截（AWARDED/CLOSED/CANCELLED）。"""
    return status not in BLOCKING_ACTIONABILITY
