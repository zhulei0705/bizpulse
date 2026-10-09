from fastapi import APIRouter

from app.api.v1.endpoints import (
    collection,
    collection_campaigns,
    companies,
    contacts,
    dashboard,
    data_growth,
    experiments,
    ingest,
    interactions,
    jobs,
    logs,
    markets,
    opportunities,
    opportunity_candidates,
    pain_points,
    quotes,
    signal_analysis,
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
api_router.include_router(contacts.contact_router)
api_router.include_router(signals.router)
api_router.include_router(signal_analysis.router)
api_router.include_router(pain_points.router)
api_router.include_router(opportunities.router)
api_router.include_router(opportunity_candidates.router)
api_router.include_router(experiments.router)
api_router.include_router(experiments.target_router)
api_router.include_router(interactions.router)
api_router.include_router(quotes.router)
api_router.include_router(sources.router)
api_router.include_router(source_records.router)
api_router.include_router(jobs.router)
api_router.include_router(logs.router)
api_router.include_router(collection_campaigns.router)
api_router.include_router(data_growth.router)
