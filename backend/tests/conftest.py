import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./data/bizpulse_test.db"
os.environ["NO_FAKE_DATA"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db import model_imports  # noqa: F401
from app.db.session import engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    # Windows 下必须先释放连接池才能删除 SQLite 文件
    import gc
    gc.collect()
    engine.dispose()
    gc.collect()
    Path("data/bizpulse_test.db").unlink(missing_ok=True)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def isolate_http_snapshots(monkeypatch, tmp_path):
    """测试正文只写 pytest 临时目录，不能触碰正式 SourceRecord 快照。"""
    from app.collectors import web
    monkeypatch.setattr(web, "BASE_DIR", tmp_path)
    from app.services import evidence_integrity
    monkeypatch.setattr(evidence_integrity, 'BASE_DIR', tmp_path)
