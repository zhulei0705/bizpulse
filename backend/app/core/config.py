from functools import lru_cache
from pathlib import Path
from pydantic import Field
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
    cors_origins: str = "http://localhost:5173"

    no_fake_data: bool = True
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





@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    Path(settings.log_dir).mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
