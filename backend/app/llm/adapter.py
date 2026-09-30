"""LLM Adapter：规则引擎之上的可选 AI 增强层。

设计原则：
- 未配置 LLM_API_KEY 时返回 None，系统照常运行（前端显示“AI分析未配置”）。
- 所有输出必须是结构化 JSON，并携带 confidence / evidence / inference。
- 任何 LLM 异常都不允许中断采集主流程。
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.llm_run import LLMRun

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMInsight:
    """LLM 单条结构化输出。inference 永远是“AI推断”，不得当作事实。"""

    kind: str  # signal | pain_point | opportunity
    title: str
    inference: str
    evidence_excerpt: str
    confidence: int
    payload: dict[str, Any]


def llm_configured() -> bool:
    return bool(settings.llm_api_key and settings.llm_base_url and settings.llm_model)


class LLMAdapter:
    """OpenAI 兼容 chat.completions 接口的薄封装。"""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _chat(self, system: str, user: str) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    def _run(self, db: Session, module: str, prompt_name: str, system: str, user: str, target_type: str | None, target_id: str | None) -> list[LLMInsight]:
        input_hash = hashlib.sha256(user.encode("utf-8")).hexdigest()
        started = __import__("time").perf_counter()
        run = LLMRun(module=module, prompt_name=prompt_name, prompt_version="v1", model=self.model, provider="openai-compatible", target_type=target_type, target_id=target_id, input_hash=input_hash)
        db.add(run)
        try:
            data = self._chat(system, user)
            items = data.get("items", [])
            insights = [
                LLMInsight(
                    kind=str(item.get("kind", module)),
                    title=str(item.get("title", ""))[:500],
                    inference=str(item.get("inference", "")),
                    evidence_excerpt=str(item.get("evidence_excerpt", "")),
                    confidence=max(0, min(int(item.get("confidence", 0)), 100)),
                    payload=item,
                )
                for item in items
                if isinstance(item, dict) and item.get("title")
            ]
            run.output_json = {"items": [i.payload for i in insights]}
            run.status = "SUCCESS"
        except Exception as exc:  # noqa: BLE001 —— LLM 失败不允许阻塞采集
            run.status = "FAILED"
            run.error_message = str(exc)[:2000]
            db.commit()
            logger.warning("LLM run failed: %s", exc)
            return []
        run.duration_seconds = __import__("time").perf_counter() - started
        db.commit()
        return insights

    def extract_signals_v2(self, db: Session, source_text: str, source_type: str | None = None, company_context: str | None = None, target_type: str | None = None, target_id: str | None = None) -> list[dict[str, Any]]:
        """T04 结构化信号提取：输出 Structured JSON（含 evidence_text/fields/fact/inference）。

        evidence_text 校验由调用方（SignalExtractor）执行 —— 找不到原文的条目不得自动批准。
        """
        from app.analyzers.prompts import SIGNAL_EXTRACTOR_SYSTEM, SIGNAL_EXTRACTOR_V1
        user = f"来源类型：{source_type or '未知'}\n企业上下文：{company_context or '无'}\n\n原始文本：\n{source_text[:12000]}"
        return self._run_structured(db, "signal_extraction_v2", SIGNAL_EXTRACTOR_V1, SIGNAL_EXTRACTOR_SYSTEM, user, target_type, target_id)

    def _run_structured(self, db: Session, module: str, prompt_name: str, prompt_version: str, system: str, user: str, target_type: str | None, target_id: str | None) -> list[dict[str, Any]]:
        """运行并返回原始结构化 items（不映射为 LLMInsight，保留 fields 等结构）。"""
        input_hash = hashlib.sha256(user.encode("utf-8")).hexdigest()
        started = __import__("time").perf_counter()
        run = LLMRun(module=module, prompt_name=prompt_name, prompt_version=prompt_version, model=self.model, provider="openai-compatible", target_type=target_type, target_id=target_id, input_hash=input_hash)
        db.add(run)
        try:
            data = self._chat(system, user)
            items = data.get("items", [])
            items = [item for item in items if isinstance(item, dict)]
            run.output_json = {"items": items}
            run.status = "SUCCESS"
        except Exception as exc:  # noqa: BLE001 —— LLM 失败不允许阻塞分析流程
            run.status = "FAILED"
            run.error_message = str(exc)[:2000]
            db.commit()
            logger.warning("LLM structured run failed: %s", exc)
            return []
        run.duration_seconds = __import__("time").perf_counter() - started
        db.commit()
        return items

    def extract_signal(self, db: Session, page_title: str, page_text: str, target_type: str | None = None, target_id: str | None = None) -> list[LLMInsight]:
        system = (
            "你是商业信号提取器。只根据给定网页文本提取真实发生的商业事件，禁止编造。"
            '输出 JSON：{"items":[{"kind":"signal","title":"...","inference":"...","evidence_excerpt":"原文摘录","confidence":0-100}]}。'
            "没有可靠信号时输出空数组。"
        )
        return self._run(db, "signal_extraction", "extract_signal_v1", system, f"标题：{page_title}\n\n正文：\n{page_text[:12000]}", target_type, target_id)

    def infer_pain_point(self, db: Session, company_name: str, signals_text: str, target_type: str | None = None, target_id: str | None = None) -> list[LLMInsight]:
        system = (
            "你是痛点分析师。基于真实商业信号推断企业可能存在的业务痛点，全部输出必须标记为推断。"
            '输出 JSON：{"items":[{"kind":"pain_point","title":"...","inference":"...","evidence_excerpt":"支撑信号摘录","confidence":0-100}]}'
        )
        return self._run(db, "pain_inference", "infer_pain_v1", system, f"企业：{company_name}\n信号：\n{signals_text[:12000]}", target_type, target_id)

    def generate_opportunity(self, db: Session, company_name: str, pains_text: str, target_type: str | None = None, target_id: str | None = None) -> list[LLMInsight]:
        system = (
            "你是商业机会生成器。基于痛点假设生成可验证的商业机会假设（AI推断，需人工审核）。"
            '输出 JSON：{"items":[{"kind":"opportunity","title":"...","inference":"建议方案","evidence_excerpt":"触发事件","confidence":0-100}]}'
        )
        return self._run(db, "opportunity_generation", "gen_opportunity_v1", system, f"企业：{company_name}\n痛点：\n{pains_text[:12000]}", target_type, target_id)


def get_llm_adapter() -> LLMAdapter | None:
    if not llm_configured():
        return None
    return LLMAdapter(str(settings.llm_api_key), str(settings.llm_base_url), str(settings.llm_model))
