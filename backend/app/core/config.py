from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "BizPulse"
    app_display_name: str = "商脉 BizPulse"
    app_version: str = "0.1.0"
    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"

    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'bizpulse.db').as_posix()}"
    log_level: str = "INFO"
    log_dir: str = str(BASE_DIR / "logs")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    no_fake_data: bool = True
    real_data_only: bool = True
    no_fake_evidence: bool = True
    no_unverified_fact: bool = True
    no_auto_approval: bool = True

    @field_validator('no_auto_approval')
    @classmethod
    def enforce_no_auto_approval(cls, value):
        # 先由 bool 类型解析环境字符串 true，再执行不可关闭的阶段门禁。
        if not value:raise ValueError('T10-C1.1 阶段 NO_AUTO_APPROVAL 必须为 TRUE')
        return True
    default_page_size: int = 20
    max_page_size: int = 100

    # LLM Adapter：未配置时系统必须照常运行（AI分析未配置）。
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = 30.0

    # 手动 URL 采集安全限制（SSRF 防护 / 资源上限）
    ingest_user_agent: str = "BizPulseBot/0.1 (+local commercial intelligence research; respects robots and auth)"
    ingest_timeout_seconds: float = 20.0
    ingest_max_redirects: int = 5
    ingest_max_bytes: int = 5_000_000
    ingest_max_text_chars: int = 200_000

    # T03：采集调度（默认关闭，避免开发环境自动访问网络）
    enable_scheduler: bool = False

    # T04：Signal 置信度权重（来源30/Evidence30/规则15/LLM15/企业10，可配置不硬编码）
    signal_confidence_weights: dict = {
        "source": 0.30, "evidence": 0.30, "rule": 0.15, "llm": 0.15, "company": 0.10,
    }
    # T04：去重时间窗口（天）—— 同事件窗口内合并，不永久合并
    signal_dedup_window_days: int = 14
    # T04：Signal 自动批准门槛（confidence≥85 且来源 A/B 且证据原文可寻）
    signal_auto_approve_threshold: int = 85

    # T08.2 Reachability 渠道权重（任务书二十：官网公开邮箱 > 官方表单 > 仅总机电话）
    reachability_weights: dict = {
        "VERIFIED_EMAIL": 80,
        "VERIFIED_FORM": 65,
        "VERIFIED_PHONE": 55,
        "UNVERIFIED": 40,
        "WEBSITE_ONLY": 45,
    }

    # T05：Opportunity 总评分权重（Pain25/Budget20/Intent20/Urgency10/AgentFit10/Reach5/Evidence10）
    opportunity_score_weights: dict = {
        "pain": 0.25, "budget": 0.20, "intent": 0.20, "urgency": 0.10,
        "agent_fit": 0.10, "reachability": 0.05, "evidence": 0.10,
    }
    # T05：Intent Score 组成（直接购买信号40/问题证据20/近期变化15/多信号支持15/来源质量10）
    intent_score_weights: dict = {
        "direct_purchase": 0.40, "problem_evidence": 0.20, "recent_change": 0.15,
        "multi_signal": 0.15, "source_quality": 0.10,
    }
    # T05：Evidence Gate —— Evidence Score < 60 时 Opportunity 等级最高 B
    evidence_gate_threshold: int = 60
    # T05：等级阈值（S/A/B/C/D）
    opportunity_grade_thresholds: dict = {"S": 90, "A": 80, "B": 70, "C": 60}
    # T05：进入机会分析的最低条件（Approved Signal ≥ 1 且 Evidence ≥ 1）
    opportunity_min_approved_signals: int = 1
    opportunity_min_evidences: int = 1
    # T05：机会去重窗口（天）：同 fingerprint 窗口内更新不新建
    opportunity_dedup_window_days: int = 14
    # T05：机会过期（天）：无新 Signal 超过该天数可进入 STALE
    opportunity_stale_days: int = 90
    # T05：V1 候选机会不自动批准 —— 全部进入 REVIEW（数据积累后再自动化）
    opportunity_auto_approve: bool = False
    # T05：Signal 时间密度窗口（天）
    signal_density_windows: list = [7, 30, 90]





@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    Path(settings.log_dir).mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
