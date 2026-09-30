from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.experiment import Interaction


def experiment_metrics(db: Session, experiment_id: str) -> dict:
    interactions = db.scalars(select(Interaction).where(Interaction.experiment_id == experiment_id)).all()
    contacted = len(interactions)
    replied = sum(1 for x in interactions if x.response_type not in (None, "NO_RESPONSE"))
    meetings = sum(1 for x in interactions if x.meeting)
    quotes = sum(1 for x in interactions if x.quote_amount is not None)
    deals = sum(1 for x in interactions if x.deal)
    revenue = sum((x.revenue or Decimal("0") for x in interactions), Decimal("0"))
    denominator = contacted or 1
    return {
        "contacted": contacted,
        "replied": replied,
        "meetings": meetings,
        "quotes": quotes,
        "deals": deals,
        "revenue": revenue,
        "reply_rate": round(replied / denominator * 100, 2) if contacted else 0,
        "meeting_rate": round(meetings / denominator * 100, 2) if contacted else 0,
        "quote_rate": round(quotes / denominator * 100, 2) if contacted else 0,
        "close_rate": round(deals / denominator * 100, 2) if contacted else 0,
    }
