from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.models.experiment import Experiment, Interaction
from app.models.opportunity import Opportunity
from app.schemas.experiment import ExperimentCreate, ExperimentRead, InteractionCreate
from app.services.audit import write_audit
from app.services.metrics import experiment_metrics

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("")
def list_experiments(
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    filters = [Experiment.status == status] if status else []
    total = db.scalar(select(func.count()).select_from(Experiment).where(*filters)) or 0
    items = db.scalars(select(Experiment).where(*filters).order_by(Experiment.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"success": True, "data": {"items": [ExperimentRead.model_validate(x).model_dump() for x in items], "total": total, "page": page, "page_size": page_size}, "message": None}


@router.post("")
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db)) -> dict:
    exp = Experiment(**payload.model_dump())
    db.add(exp)
    db.flush()
    write_audit(db, "CREATE", "experiment", exp.id, {"name": exp.name})
    db.commit()
    db.refresh(exp)
    return {"success": True, "data": ExperimentRead.model_validate(exp).model_dump(), "message": None}


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str, db: Session = Depends(get_db)) -> dict:
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    data = ExperimentRead.model_validate(exp).model_dump()
    data["metrics"] = experiment_metrics(db, experiment_id)
    return {"success": True, "data": data, "message": None}


@router.post("/{experiment_id}/interactions")
def add_interaction(experiment_id: str, payload: InteractionCreate, db: Session = Depends(get_db)) -> dict:
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if not db.get(Company, payload.company_id):
        raise HTTPException(status_code=422, detail="company_id does not exist")
    if payload.opportunity_id and not db.get(Opportunity, payload.opportunity_id):
        raise HTTPException(status_code=422, detail="opportunity_id does not exist")
    data = payload.model_dump()
    data["experiment_id"] = experiment_id
    interaction = Interaction(**data)
    db.add(interaction)
    db.flush()
    write_audit(db, "CREATE", "interaction", interaction.id, {"experiment_id": experiment_id})
    db.commit()
    return {"success": True, "data": {"id": interaction.id}, "message": None}
