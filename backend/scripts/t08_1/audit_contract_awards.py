"""T08.1 阶段A：CONTRACT_AWARD 信号语义审计（正式库全部待审核中标信号）。

原则（任务书 T08.1）：
- 逐条解析 buyer/awarded_supplier/project/amount/announcement_date/procurement_method/category，
  原文不存在 → null，禁止猜测；
- 判定主体角色 subject_role（采购方与中标方绝对不能混）；
- 判定 Procurement Lifecycle 与 Opportunity actionability_status；
- 回填缺失的 SignalEvidence（原文精确子串，禁止编造）；
- 修复 published_at（以公告时间为准，修正"招标公告发布日期"误判）；
- 只产出 recommended_review_action（APPROVE/REJECT/NEED_REVIEW/SUPERSEDE），不修改 signal.status；
  最终审批由 apply_signal_review.py 在人工抽查通过后按规则执行。

用法：
    python scripts/t08_1/audit_contract_awards.py            # 执行审计并写入 payload/evidence + 生成报告
    python scripts/t08_1/audit_contract_awards.py --dry-run  # 只输出报告，不写库
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.db import model_imports  # noqa: F401,E402  确保全部 ORM 关系可解析
from app.db.session import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.signal import Signal, SignalEvidence  # noqa: E402
from app.models.source import Source, SourceRecord  # noqa: E402
from app.services import procurement_parser as pp  # noqa: E402
from app.services.audit import write_audit  # noqa: E402

REPORT_DIR = ROOT / "docs" / "reports"


def _norm(name: str | None) -> str:
    return "".join((name or "").lower().split())


def audit_one(signal: Signal, record: SourceRecord, source: Source, company: Company) -> dict:
    """对单条 CONTRACT_AWARD 信号做结构化语义审计（不改状态）。"""
    text = record.raw_text or ""
    subject_name = company.company_name if company else None

    announcement_time = pp.parse_announcement_time(text)
    buyer_info = pp.parse_buyer_organization(text)
    suppliers = pp.parse_awarded_suppliers_with_amounts(text)
    total_amount = pp.parse_total_award_amount(text)
    method = pp.parse_procurement_method(text)
    project_name = pp.parse_project_name(text)
    category = pp.parse_category(text)
    deadline = pp.parse_deadline(text)
    lifecycle = pp.parse_procurement_lifecycle(text, deadline=deadline)

    role = pp.classify_subject_role(subject_name, buyer_info, suppliers)
    actionability = pp.derive_actionability(lifecycle, role)

    # 主体对应的供应商条目（金额按主体单家取，不用公告总额冒充）
    subject_supplier = None
    if role == "SUPPLIER":
        for s in suppliers:
            if _norm(s["supplier_name"]) == _norm(subject_name):
                subject_supplier = s
                break

    evidence_snippet = pp.extract_award_evidence_snippet(text, subject_name or "")
    evidence_quality = "PASS" if evidence_snippet and _norm(subject_name or "") in _norm(evidence_snippet) else "FAIL"

    url_host = (record.url or "").lower()
    grade_a = (source.reliability_grade or "").upper() == "A"
    url_ok = url_host.startswith("http") and "ccgp.gov.cn" in url_host

    # 审计发现（严重问题列表）
    findings: list[str] = []
    if role == "OTHER":
        findings.append("主体公司未在公告的供应商/采购人/代理机构中匹配到（主体挂错风险）")
    if company and company.organization_type == "SOURCE_PLATFORM":
        findings.append("主体是数据来源平台（SOURCE_PLATFORM），不得作为业务企业")
    if evidence_quality == "FAIL":
        findings.append("无法从原文截取包含主体的精确证据片段")
    if not suppliers:
        findings.append("公告中未解析到中标供应商声明")
    if role == "SUPPLIER" and subject_supplier is None:
        findings.append("主体在供应商列表中名称不完全一致")

    # 推荐动作（只是推荐；审批由独立脚本按规则执行）
    if findings:
        recommended = "REJECT" if (role == "OTHER" or (company and company.organization_type == "SOURCE_PLATFORM")) else "NEED_REVIEW"
    elif role == "SUPPLIER" and grade_a and url_ok and evidence_quality == "PASS" and lifecycle == "AWARDED":
        recommended = "APPROVE"
    else:
        recommended = "NEED_REVIEW"

    audit_payload = {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "audit_version": "T08.1",
        "source_url": record.url,
        "source_record_id": record.id,
        "source_grade": source.reliability_grade,
        "project_name": project_name,
        "buyer_organization": buyer_info.get("buyer"),
        "executing_agency": buyer_info.get("executing_agency"),
        "procurement_agency": buyer_info.get("procurement_agency"),
        "awarded_supplier": subject_supplier["supplier_name"] if subject_supplier else None,
        "award_amount": subject_supplier["award_amount"] if subject_supplier else None,
        "currency": subject_supplier["currency"] if subject_supplier else None,
        "amount_raw": subject_supplier["amount_raw"] if subject_supplier else None,
        "amount_source": (subject_supplier or {}).get("amount_source", "PER_SUPPLIER" if subject_supplier and subject_supplier["award_amount"] is not None else None),
        "discount_rate": (subject_supplier or {}).get("discount_rate"),
        "total_award_amount": total_amount,
        "announcement_date": announcement_time.isoformat() if announcement_time else None,
        "procurement_method": method,
        "project_category": category,
        "subject_company": subject_name,
        "subject_role": role,
        "evidence_text": evidence_snippet,
        "evidence_quality": evidence_quality,
        "procurement_status": lifecycle,
        "actionability_status": actionability,
        "findings": findings,
        "recommended_review_action": recommended,
    }
    return audit_payload


def main(dry_run: bool = False) -> None:
    db = SessionLocal()
    try:
        signals = db.scalars(select(Signal).where(
            Signal.signal_type == "CONTRACT_AWARD",
            Signal.status.in_(["VALID", "REVIEW"]),
        )).all()
        results: list[dict] = []
        published_fixed = 0
        records_fixed = 0
        evidences_created = 0

        for signal in signals:
            record = db.get(SourceRecord, signal.source_record_id)
            source = db.get(Source, record.source_id) if record else None
            company = db.get(Company, signal.company_id) if signal.company_id else None
            if record is None or source is None or company is None:
                results.append({
                    "signal_id": signal.id, "title": signal.title,
                    "error": "missing source_record/source/company",
                    "recommended_review_action": "NEED_REVIEW",
                })
                continue

            audit_payload = audit_one(signal, record, source, company)
            results.append({"signal_id": signal.id, "title": signal.title, **audit_payload})

            if not dry_run:
                # 1) payload_json 记录审计结构（不覆盖既有键）
                payload = dict(signal.payload_json or {})
                payload["t08_audit"] = audit_payload
                signal.payload_json = payload
                # 2) published_at 修复：以公告时间为准（真实原文数据）
                announcement = audit_payload.get("announcement_date")
                if announcement:
                    parsed_dt = datetime.fromisoformat(announcement)
                    if signal.published_at != parsed_dt:
                        signal.published_at = parsed_dt
                        published_fixed += 1
                    if record.published_at != parsed_dt:
                        record.published_at = parsed_dt
                        record.metadata_json = {**(record.metadata_json or {}),
                                                "published_at_fixed_by": "T08.1_audit",
                                                "published_at_reason": "公告时间重解析（修正招标公告发布日期误判）"}
                        records_fixed += 1
                # 3) 回填缺失的 SignalEvidence（原文精确子串）
                snippet = audit_payload.get("evidence_text")
                if snippet:
                    existing = db.scalar(select(SignalEvidence).where(
                        SignalEvidence.signal_id == signal.id,
                        SignalEvidence.source_record_id == record.id,
                    ))
                    if existing is None:
                        offset = (record.raw_text or "").find(snippet)
                        db.add(SignalEvidence(
                            signal_id=signal.id,
                            source_record_id=record.id,
                            quoted_text=snippet,
                            start_offset=offset if offset >= 0 else None,
                            end_offset=(offset + len(snippet)) if offset >= 0 else None,
                            evidence_type="ORIGINAL_TEXT",
                            confidence=85,
                            verification_status="VERIFIED" if offset >= 0 else "UNVERIFIED",
                        ))
                        evidences_created += 1
                write_audit(db, "T08_SIGNAL_AUDITED", "signal", signal.id, {
                    "subject_role": audit_payload["subject_role"],
                    "procurement_status": audit_payload["procurement_status"],
                    "actionability_status": audit_payload["actionability_status"],
                    "recommended_review_action": audit_payload["recommended_review_action"],
                    "evidence_quality": audit_payload["evidence_quality"],
                })

        if not dry_run:
            db.commit()

        # 汇总统计
        summary = {
            "total": len(results),
            "approve": sum(1 for r in results if r.get("recommended_review_action") == "APPROVE"),
            "reject": sum(1 for r in results if r.get("recommended_review_action") == "REJECT"),
            "need_review": sum(1 for r in results if r.get("recommended_review_action") == "NEED_REVIEW"),
            "supersede": sum(1 for r in results if r.get("recommended_review_action") == "SUPERSEDE"),
            "subject_role": {},
            "procurement_status": {},
            "actionability": {},
            "evidence_pass": sum(1 for r in results if r.get("evidence_quality") == "PASS"),
            "amount_present": sum(1 for r in results if r.get("award_amount") is not None),
            "buyer_parsed": sum(1 for r in results if r.get("buyer_organization")),
            "published_fixed": published_fixed,
            "records_fixed": records_fixed,
            "evidences_created": evidences_created,
            "dry_run": dry_run,
        }
        for r in results:
            for key, bucket in (("subject_role", "subject_role"), ("procurement_status", "procurement_status"), ("actionability_status", "actionability")):
                v = r.get(key) or "UNKNOWN"
                summary[bucket][v] = summary[bucket].get(v, 0) + 1

        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "T08.1_contract_award_audit.json").write_text(
            json.dumps({"summary": summary, "items": results}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        write_markdown_report(summary, results)

        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        db.close()


def write_markdown_report(summary: dict, results: list[dict]) -> None:
    lines = [
        "# T08.1 阶段A — CONTRACT_AWARD 信号语义审计报告",
        "",
        f"生成时间：{datetime.now(timezone.utc).isoformat()}",
        "",
        "## 汇总",
        "",
        f"- 审计信号总数：{summary['total']}",
        f"- 推荐 APPROVE：{summary['approve']}",
        f"- 推荐 REJECT：{summary['reject']}",
        f"- 推荐 NEED_REVIEW：{summary['need_review']}",
        f"- 推荐 SUPERSEDE：{summary['supersede']}",
        f"- 主体角色分布：{json.dumps(summary['subject_role'], ensure_ascii=False)}",
        f"- 生命周期分布：{json.dumps(summary['procurement_status'], ensure_ascii=False)}",
        f"- 可行动性分布：{json.dumps(summary['actionability'], ensure_ascii=False)}",
        f"- Evidence 通过：{summary['evidence_pass']}/{summary['total']}",
        f"- 金额解析成功：{summary['amount_present']}/{summary['total']}",
        f"- 采购方解析成功：{summary['buyer_parsed']}/{summary['total']}",
        f"- published_at 修复：{summary['published_fixed']} 条信号 / {summary['records_fixed']} 条来源记录",
        f"- 回填 Evidence：{summary['evidences_created']} 条",
        "",
        "## 逐条明细",
        "",
        "| signal_id | 项目 | 采购方 | 中标供应商(主体) | 金额(元) | 公告时间 | 角色 | 生命周期 | 可行动性 | 推荐 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        amount = r.get("award_amount")
        amount_str = f"{amount:,.2f}" if isinstance(amount, (int, float)) else (
            f"折扣率{r.get('discount_rate')}%" if r.get("discount_rate") else "null")
        lines.append(
            f"| {r.get('signal_id')} | {(r.get('project_name') or 'null')[:38]} | {(r.get('buyer_organization') or 'null')[:28]} "
            f"| {(r.get('awarded_supplier') or r.get('subject_company') or 'null')[:28]} | {amount_str} "
            f"| {(r.get('announcement_date') or 'null')[:16]} | {r.get('subject_role')} | {r.get('procurement_status')} "
            f"| {r.get('actionability_status')} | **{r.get('recommended_review_action')}** |"
        )
    findings = [r for r in results if r.get("findings")]
    if findings:
        lines += ["", "## 审计发现（需人工复核）", ""]
        for r in findings:
            lines.append(f"- `{r.get('signal_id')}` {r.get('title', '')[:60]}：{'；'.join(r['findings'])}")
    (REPORT_DIR / "T08.1_contract_award_audit.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
