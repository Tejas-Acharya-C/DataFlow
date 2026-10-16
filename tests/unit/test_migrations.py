"""Unit tests for Alembic migration execution and configuration isolation."""

import os
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_explicit_alembic_url_not_overwritten():
    """Verify that migrations/env.py respects an explicitly supplied Alembic URL.

    Ensures that running migrations against a custom test database URL does not
    get hijacked by application settings or point to the development database.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = f.name

    try:
        custom_url = f"sqlite:///{Path(temp_db_path).as_posix()}"
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", custom_url)

        # Run migration on isolated temporary SQLite database
        command.upgrade(alembic_cfg, "head")

        # Verify tables were created in the temporary database
        engine = create_engine(custom_url)
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        assert "processing_jobs" in table_names
        assert "validation_rejections" in table_names
        assert "ingestion_checkpoints" in table_names
        assert "datasets" in table_names

        # Verify that alembic_cfg's configured URL remained the custom URL
        assert alembic_cfg.get_main_option("sqlalchemy.url") == custom_url

        # Test safe downgrade on isolated database
        command.downgrade(alembic_cfg, "base")
        inspector_after = inspect(engine)
        assert "processing_jobs" not in inspector_after.get_table_names()
        engine.dispose()
    finally:
        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except OSError:
                pass
