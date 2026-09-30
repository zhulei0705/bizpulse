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
    engine.dispose()
    Path("data/bizpulse_test.db").unlink(missing_ok=True)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
