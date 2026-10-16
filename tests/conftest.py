from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from yeg311.config import PROJECT_ROOT, Settings
from yeg311.sample import write_sample
from yeg311.warehouse import build_warehouse

PINNED_TODAY = date(2026, 10, 15)


@pytest.fixture(scope="session")
def settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    data_dir = tmp_path_factory.mktemp("data")
    s = Settings(project_root=PROJECT_ROOT, data_dir=data_dir)
    s.ensure_dirs()
    return s


@pytest.fixture(scope="session")
def built_warehouse(settings: Settings) -> dict:
    """Synthetic sample -> full warehouse build, shared by the read-only tests."""
    write_sample(settings, n_rows=6_000, seed=7, today=PINNED_TODAY)
    return build_warehouse(settings)


@pytest.fixture()
def con(built_warehouse: dict, settings: Settings) -> duckdb.DuckDBPyConnection:
    c = duckdb.connect(str(settings.warehouse_path), read_only=True)
    yield c
    c.close()


@pytest.fixture()
def raw_dir(settings: Settings, built_warehouse: dict) -> Path:
    return settings.raw_dir
