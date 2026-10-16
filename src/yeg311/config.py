"""Central configuration for the yeg311 pipeline.

Everything that could reasonably change between environments (paths, dataset id,
page size, lookback window) lives here and can be overridden with environment
variables, so the same code runs on a laptop, in CI and in a scheduled job.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Source dataset: City of Edmonton Open Data Portal (Socrata / SODA 2.1 API)
# "311 Requests" -> https://data.edmonton.ca/d/q7ua-agfg
# Rolling window: current calendar year + previous two calendar years.
# ---------------------------------------------------------------------------
SOCRATA_DOMAIN = "data.edmonton.ca"
DATASET_ID = "q7ua-agfg"
DATASET_URL = f"https://{SOCRATA_DOMAIN}/resource/{DATASET_ID}.json"
DATASET_LANDING_PAGE = f"https://{SOCRATA_DOMAIN}/d/{DATASET_ID}"

# Columns we actually need. The portal also publishes pre-concatenated helper
# columns (e.g. "service_area_service_category") and nested location structs;
# we derive those ourselves instead of carrying redundant payload.
RAW_COLUMNS: tuple[str, ...] = (
    "row_id",
    "date_created",
    "date_closed",
    "request_status",
    "status_detail",
    "service_area",
    "service_category",
    "service_description",
    "interaction_channel",
    "referral_type",
    "neighbourhood_id",
    "neighbourhood",
    "ward",
    "nbhd_latitude",
    "nbhd_longitude",
    "ward_latitude",
    "ward_longitude",
)

PROJECT_ROOT = Path(os.environ.get("YEG311_PROJECT_ROOT", Path(__file__).resolve().parents[2]))


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


@dataclass(slots=True)
class Settings:
    """Runtime settings. Construct once in the CLI and pass around explicitly."""

    project_root: Path = PROJECT_ROOT
    data_dir: Path = field(default=None)  # type: ignore[assignment]
    raw_dir: Path = field(default=None)  # type: ignore[assignment]
    warehouse_path: Path = field(default=None)  # type: ignore[assignment]
    export_dir: Path = field(default=None)  # type: ignore[assignment]
    sql_dir: Path = field(default=None)  # type: ignore[assignment]
    seeds_dir: Path = field(default=None)  # type: ignore[assignment]

    app_token: str | None = field(default_factory=lambda: os.environ.get("SOCRATA_APP_TOKEN") or None)
    page_size: int = field(default_factory=lambda: _env_int("YEG311_PAGE_SIZE", 50_000))
    lookback_months: int = field(default_factory=lambda: _env_int("YEG311_LOOKBACK_MONTHS", 3))
    request_timeout_s: int = field(default_factory=lambda: _env_int("YEG311_TIMEOUT_S", 120))

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root)
        self.data_dir = Path(os.environ.get("YEG311_DATA_DIR", self.data_dir or self.project_root / "data"))
        self.raw_dir = Path(self.raw_dir or self.data_dir / "raw" / "311_requests")
        self.warehouse_path = Path(self.warehouse_path or self.data_dir / "warehouse" / "yeg311.duckdb")
        self.export_dir = Path(self.export_dir or self.data_dir / "exports")
        self.sql_dir = Path(self.sql_dir or self.project_root / "sql")
        self.seeds_dir = Path(self.seeds_dir or self.project_root / "seeds")

    @property
    def raw_glob(self) -> str:
        """Hive-partitioned parquet glob consumed by the bronze layer."""
        return str(self.raw_dir / "year=*" / "month=*" / "*.parquet")

    def ensure_dirs(self) -> None:
        for p in (self.raw_dir, self.warehouse_path.parent, self.export_dir):
            p.mkdir(parents=True, exist_ok=True)
