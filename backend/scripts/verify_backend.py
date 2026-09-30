from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app

PATHS = [
    "/api/v1/health",
    "/api/v1/system/info",
    "/api/v1/dashboard",
    "/api/v1/companies",
    "/api/v1/markets",
    "/api/v1/signals",
    "/api/v1/opportunities",
    "/api/v1/experiments",
    "/api/v1/sources",
    "/api/v1/jobs",
    "/api/v1/logs/llm-runs",
]

with TestClient(app) as client:
    failed = []
    for path in PATHS:
        response = client.get(path)
        print(f"{response.status_code} {path}")
        if response.status_code != 200:
            failed.append(path)

if failed:
    raise SystemExit(f"Verification failed: {failed}")
print("All BizPulse backend checks passed.")
