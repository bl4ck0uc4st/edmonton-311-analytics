"""Warehouse build: bronze -> silver -> gold inside DuckDB.

The transformations themselves live in ``sql/*.sql`` (version-controlled, reviewable SQL);
this module only orders them, injects a few parameters and records build metadata.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import holidays

from .config import Settings

log = logging.getLogger(__name__)

PIPELINE_VERSION = "1.0.0"


def connect(settings: Settings, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    settings.warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(settings.warehouse_path), read_only=read_only)


def _sql_files(sql_dir: Path) -> list[Path]:
    """Numbered top-level SQL files, executed in lexical order (00_, 10_, 20_, ...)."""
    files = sorted(p for p in sql_dir.glob("*.sql") if re.match(r"^\d{2}_", p.name))
    if not files:
        raise FileNotFoundError(f"no numbered .sql files found in {sql_dir}")
    return files


def load_seeds(con: duckdb.DuckDBPyConnection, seeds_dir: Path, years: range) -> None:
    """Load reference CSVs plus an Alberta statutory-holiday calendar into the seed schema."""
    con.execute("CREATE SCHEMA IF NOT EXISTS seed")
    con.execute(
        """
        CREATE OR REPLACE TABLE seed.service_groups AS
        SELECT nullif(trim(service_area), '') AS service_area,
               nullif(trim(service_group), '') AS service_group
        FROM read_csv(?, header = true, all_varchar = true)
        """,
        [str(seeds_dir / "service_groups.csv")],
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE seed.sla_targets AS
        SELECT nullif(trim(service_area), '')     AS service_area,
               nullif(trim(service_category), '') AS service_category,
               CAST(target_days AS INTEGER)       AS target_days,
               nullif(trim(basis), '')            AS basis
        FROM read_csv(?, header = true, all_varchar = true)
        """,
        [str(seeds_dir / "sla_targets.csv")],
    )
    ab = holidays.country_holidays("CA", subdiv="AB", years=years)
    rows = sorted((d, name) for d, name in ab.items())
    con.execute("CREATE OR REPLACE TABLE seed.holidays (holiday_date DATE, holiday_name VARCHAR)")
    if rows:
        con.executemany("INSERT INTO seed.holidays VALUES (?, ?)", rows)
    log.info("Seeds loaded: %d service groups, %d SLA targets, %d holidays", *_seed_counts(con))


def _seed_counts(con: duckdb.DuckDBPyConnection) -> tuple[int, int, int]:
    return tuple(  # type: ignore[return-value]
        con.execute(f"SELECT count(*) FROM seed.{t}").fetchone()[0]
        for t in ("service_groups", "sla_targets", "holidays")
    )


def build_warehouse(settings: Settings, as_of: datetime | None = None) -> dict:
    """Run every numbered SQL step and return a summary dict (also stored in meta.build_info)."""
    raw_files = glob.glob(settings.raw_glob)
    if not raw_files:
        raise FileNotFoundError(
            f"No raw partitions found under {settings.raw_dir}. Run `yeg311 extract` or `yeg311 sample` first."
        )

    con = connect(settings)
    try:
        con.execute("SET threads TO 4")
        started = datetime.now(UTC)

        # 1) schemas
        con.execute((settings.sql_dir / "00_schemas.sql").read_text(encoding="utf-8"))

        # 2) bronze view (needs the glob)
        bronze_sql = (settings.sql_dir / "10_bronze_requests.sql").read_text(encoding="utf-8")
        con.execute(bronze_sql.replace("{raw_glob}", settings.raw_glob.replace("'", "''")))
        bronze_rows = con.execute("SELECT count(*) FROM bronze.requests").fetchone()[0]
        if bronze_rows == 0:
            raise RuntimeError("bronze.requests is empty; nothing to build")

        # 3) "as of" timestamp: latest request in the data unless the caller pins one
        if as_of is None:
            as_of = con.execute(
                "SELECT max(try_cast(date_created AS TIMESTAMP)) FROM bronze.requests"
            ).fetchone()[0]
        as_of_ts = as_of.strftime("%Y-%m-%d %H:%M:%S")
        as_of_date = as_of.strftime("%Y-%m-%d")

        # 4) seeds (holidays must cover the full date dimension range)
        min_year = con.execute(
            "SELECT min(year(try_cast(date_created AS TIMESTAMP))) FROM bronze.requests"
        ).fetchone()[0]
        load_seeds(con, settings.seeds_dir, years=range(int(min_year), as_of.year + 3))

        # 5) silver + gold steps
        params = {"raw_glob": settings.raw_glob, "as_of_ts": as_of_ts, "as_of_date": as_of_date}
        for path in _sql_files(settings.sql_dir):
            if path.name.startswith(("00_", "10_")):
                continue  # already executed above
            sql = path.read_text(encoding="utf-8")
            for k, v in params.items():
                sql = sql.replace("{" + k + "}", v)
            log.info("Running %s", path.name)
            con.execute(sql)

        # 6) metadata
        counts = {
            t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in (
                "silver.requests",
                "gold.dim_date",
                "gold.dim_service",
                "gold.dim_neighbourhood",
                "gold.dim_intake",
                "gold.dim_status",
                "gold.fact_service_request",
                "gold.fact_backlog_snapshot",
                "gold.agg_daily_requests",
            )
        }
        date_range = con.execute("SELECT min(created_at), max(created_at) FROM silver.requests").fetchone()
        finished = datetime.now(UTC)
        manifest_path = settings.raw_dir / "_manifest.json"
        dataset_id = ""
        if manifest_path.exists():
            dataset_id = str(json.loads(manifest_path.read_text(encoding="utf-8")).get("dataset_id", ""))
        data_source = (
            "synthetic sample (yeg311 sample)" if dataset_id.startswith("SYNTHETIC") else "data.edmonton.ca"
        )
        summary = {
            "pipeline_version": PIPELINE_VERSION,
            "data_source": data_source,
            "built_at_utc": finished.isoformat(timespec="seconds"),
            "build_seconds": round((finished - started).total_seconds(), 1),
            "as_of": as_of_ts,
            "bronze_rows": int(bronze_rows),
            "git_sha": os.environ.get("GITHUB_SHA", os.environ.get("YEG311_GIT_SHA", "local")),
            "data_min_created_at": date_range[0].isoformat(sep=" ") if date_range[0] else None,
            "data_max_created_at": date_range[1].isoformat(sep=" ") if date_range[1] else None,
            "row_counts": {k: int(v) for k, v in counts.items()},
        }
        con.execute("CREATE OR REPLACE TABLE meta.build_info (key VARCHAR, value VARCHAR)")
        flat = {
            **{k: v for k, v in summary.items() if k != "row_counts"},
            **{f"rows.{k}": v for k, v in counts.items()},
        }
        con.executemany("INSERT INTO meta.build_info VALUES (?, ?)", [(k, str(v)) for k, v in flat.items()])
        log.info(
            "Warehouse built in %ss: %s fact rows",
            summary["build_seconds"],
            f"{counts['gold.fact_service_request']:,}",
        )
        return summary
    finally:
        con.close()
