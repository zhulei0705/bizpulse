# Import every SQLAlchemy model here so Alembic sees complete metadata.
from app.models.audit import AuditLog
from app.models.company import Company, CompanyAlias, CompanyContact, CompanyMarket
from app.models.experiment import Experiment, ExperimentOpportunity, Interaction
from app.models.job import CollectionJob
from app.models.llm_run import LLMRun
from app.models.market import Market
from app.models.opportunity import Opportunity, OpportunityEvidence
from app.models.pain_point import PainPoint, PainPointEvidence
from app.models.signal import Signal
from app.models.source import Source, SourceRecord
from app.models.system import SystemConfig

__all__ = [
    "AuditLog",
    "Company",
    "CompanyAlias",
    "CompanyContact",
    "CompanyMarket",
    "Experiment",
    "ExperimentOpportunity",
    "Interaction",
    "CollectionJob",
    "LLMRun",
    "Market",
    "Opportunity",
    "OpportunityEvidence",
    "PainPoint",
    "PainPointEvidence",
    "Signal",
    "Source",
    "SourceRecord",
    "SystemConfig",
]
