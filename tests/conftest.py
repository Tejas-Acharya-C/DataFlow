"""Pytest global configuration and fixtures for DataFlow."""

import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from dataflow.config import Settings, get_settings
from dataflow.db.base import Base
from dataflow.db.session import get_db
from dataflow.main import create_app
from dataflow.storage.local import LocalStorageManager


@pytest.fixture(scope="session")
def temp_dir() -> Generator[Path, None, None]:
    """Provide temporary directory for file storage."""
    d = Path(tempfile.mkdtemp(prefix="dataflow_test_storage_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def storage(temp_dir: Path) -> LocalStorageManager:
    """Provide isolated local storage manager."""
    return LocalStorageManager(root_path=temp_dir)


@pytest.fixture
def test_db_session() -> Generator[Session, None, None]:
    """Provide fresh in-memory SQLite database session for unit tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(temp_dir: Path) -> Generator[TestClient, None, None]:
    """Provide FastAPI test client with mocked DB and storage."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_settings():
        return Settings(
            DATAFLOW_DATABASE_URL="sqlite:///:memory:",
            DATAFLOW_STORAGE_ROOT=str(temp_dir),
            ENVIRONMENT="testing",
        )

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_settings

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)
