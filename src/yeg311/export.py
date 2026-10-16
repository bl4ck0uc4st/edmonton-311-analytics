"""Export the gold layer to files Power BI (and anything else) can read.

Why files and not a live DuckDB connection? Power BI Desktop has first-class Parquet
and CSV connectors and no DuckDB connector out of the box. Publishing the star schema as
Parquet (plus CSV for the small dimensions) keeps the dashboard portable: it refreshes
from a local folder *or* straight from the GitHub Release the scheduled workflow uploads.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .config import Settings
from .warehouse import connect

log = logging.getLogger(__name__)

# (table, export basename, also write CSV?)
EXPORTS: tuple[tuple[str, str, bool], ...] = (
    ("gold.dim_date", "dim_date", True),
    ("gold.dim_service", "dim_service", True),
    ("gold.dim_neighbourhood", "dim_neighbourhood", True),
    ("gold.dim_intake", "dim_intake", True),
    ("gold.dim_status", "dim_status", True),
    ("gold.fact_service_request", "fact_service_request", False),
    ("gold.fact_backlog_snapshot", "fact_backlog_snapshot", False),
    ("gold.agg_daily_requests", "agg_daily_requests", True),
    ("meta.quality_results", "quality_results", True),
    ("meta.build_info", "build_info", True),
)


def export_gold(settings: Settings, export_dir: Path | None = None, csv: bool = True) -> dict:
    export_dir = Path(export_dir or settings.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    con = connect(settings, read_only=True)
    manifest: dict[str, dict] = {}
    try:
        for table, name, want_csv in EXPORTS:
            exists = con.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema || '.' || table_name = ?",
                [table],
            ).fetchone()[0]
            if not exists:
                log.warning("Skipping %s (not built)", table)
                continue
            parquet_path = export_dir / f"{name}.parquet"
            con.execute(
                f"COPY (SELECT * FROM {table}) TO '{parquet_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            entry = {
                "parquet": parquet_path.name,
                "rows": int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]),
            }
            if csv and want_csv:
                csv_path = export_dir / f"{name}.csv"
                con.execute(
                    f"COPY (SELECT * FROM {table}) TO '{csv_path.as_posix()}' (FORMAT CSV, HEADER, DELIMITER ',')"
                )
                entry["csv"] = csv_path.name
            manifest[name] = entry
            log.info("Exported %s -> %s (%s rows)", table, parquet_path.name, f"{entry['rows']:,}")

        build_info = dict(con.execute("SELECT key, value FROM meta.build_info").fetchall())
    finally:
        con.close()

    metadata = {"build": build_info, "files": manifest}
    (export_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata
