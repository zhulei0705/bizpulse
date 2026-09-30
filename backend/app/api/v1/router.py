from fastapi import APIRouter

from app.api.v1.endpoints import (
    collection,
    companies,
    contacts,
    dashboard,
    experiments,
    ingest,
    jobs,
    logs,
    markets,
    opportunities,
    pain_points,
    signals,
    source_records,
    sources,
    system,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(dashboard.router)
api_router.include_router(ingest.router)
api_router.include_router(collection.router)
api_router.include_router(markets.router)
api_router.include_router(companies.router)
api_router.include_router(contacts.router)
api_router.include_router(signals.router)
api_router.include_router(pain_points.router)
api_router.include_router(opportunities.router)
api_router.include_router(experiments.router)
api_router.include_router(sources.router)
api_router.include_router(source_records.router)
api_router.include_router(jobs.router)
api_router.include_router(logs.router)
