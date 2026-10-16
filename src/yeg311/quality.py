"""Data-quality checks run against the gold layer after every build.

Each check is a SQL statement returning a single number (the count of *failing* rows or
a measured value). A check fails when ``value > threshold``. Critical failures make the
pipeline exit non-zero (so CI/scheduled runs stop before publishing bad data); warnings
are reported but do not block. Results are written to ``meta.quality_results`` and to a
JSON report that the Power BI "Data Quality" page displays.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from .config import Settings
from .warehouse import connect

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    description: str
    severity: str  # "critical" | "warning"
    sql: str
    threshold: float = 0.0
    unit: str = "rows"


CHECKS: tuple[Check, ...] = (
    Check(
        "fact_not_empty",
        "Fact table must contain rows",
        "critical",
        "SELECT CASE WHEN count(*) = 0 THEN 1 ELSE 0 END FROM gold.fact_service_request",
    ),
    Check(
        "unique_request_id",
        "request_id is unique in the fact table (de-duplication worked)",
        "critical",
        "SELECT count(*) - count(DISTINCT request_id) FROM gold.fact_service_request",
    ),
    Check(
        "no_null_created_at",
        "Every request has a creation timestamp",
        "critical",
        "SELECT count(*) FROM gold.fact_service_request WHERE created_at IS NULL",
    ),
    Check(
        "fk_service",
        "Every fact row resolves to a service dimension member",
        "critical",
        "SELECT count(*) FROM gold.fact_service_request f LEFT JOIN gold.dim_service d USING (service_key) WHERE d.service_key IS NULL",
    ),
    Check(
        "fk_neighbourhood",
        "Every fact row resolves to a neighbourhood dimension member (incl. Unknown)",
        "critical",
        "SELECT count(*) FROM gold.fact_service_request f LEFT JOIN gold.dim_neighbourhood d USING (neighbourhood_key) WHERE d.neighbourhood_key IS NULL",
    ),
    Check(
        "fk_intake",
        "Every fact row resolves to an intake dimension member",
        "critical",
        "SELECT count(*) FROM gold.fact_service_request f LEFT JOIN gold.dim_intake d USING (intake_key) WHERE d.intake_key IS NULL",
    ),
    Check(
        "fk_status",
        "Every fact row resolves to a status dimension member",
        "critical",
        "SELECT count(*) FROM gold.fact_service_request f LEFT JOIN gold.dim_status d USING (status_key) WHERE d.status_key IS NULL",
    ),
    Check(
        "fk_created_date",
        "Every created_date_key exists in dim_date",
        "critical",
        "SELECT count(*) FROM gold.fact_service_request f LEFT JOIN gold.dim_date d ON d.date_key = f.created_date_key WHERE d.date_key IS NULL",
    ),
    Check(
        "fk_closed_date",
        "Every non-null closed_date_key exists in dim_date",
        "critical",
        "SELECT count(*) FROM gold.fact_service_request f LEFT JOIN gold.dim_date d ON d.date_key = f.closed_date_key WHERE f.closed_date_key IS NOT NULL AND d.date_key IS NULL",
    ),
    Check(
        "no_negative_resolution",
        "Resolution time is never negative after cleaning",
        "critical",
        "SELECT count(*) FROM gold.fact_service_request WHERE resolution_hours < 0",
    ),
    Check(
        "open_rows_without_close_timestamp",
        "Rows reported Open never carry a close timestamp",
        "critical",
        "SELECT count(*) FROM gold.fact_service_request WHERE NOT is_closed AND closed_at IS NOT NULL",
    ),
    Check(
        "closed_without_timestamp_pct",
        "Share of Closed rows (%) whose close timestamp was missing or rejected in silver",
        "warning",
        """
        SELECT round(100.0 * count(*) FILTER (WHERE is_closed AND closed_at IS NULL)
                     / nullif(count(*) FILTER (WHERE is_closed), 0), 3)
        FROM gold.fact_service_request
        """,
        threshold=0.5,
        unit="%",
    ),
    Check(
        "closed_before_created_pct",
        "Share of rows (%) whose source close timestamp preceded creation (nulled in silver)",
        "warning",
        "SELECT round(100.0 * count(*) FILTER (WHERE closed_before_created_flag) / count(*), 3) FROM gold.fact_service_request",
        threshold=0.5,
        unit="%",
    ),
    Check(
        "missing_neighbourhood_pct",
        "Share of rows (%) without a neighbourhood (expected: mostly phone information calls)",
        "warning",
        "SELECT round(100.0 * count(*) FILTER (WHERE neighbourhood_key = -1) / count(*), 2) FROM gold.fact_service_request",
        threshold=60.0,
        unit="%",
    ),
    Check(
        "unclassified_service_pct",
        "Share of rows (%) with an unclassified service area/category",
        "warning",
        """
        SELECT round(100.0 * count(*) FILTER (WHERE d.service_area = 'Unclassified') / count(*), 3)
        FROM gold.fact_service_request f JOIN gold.dim_service d USING (service_key)
        """,
        threshold=1.0,
        unit="%",
    ),
    Check(
        "known_status_values",
        "request_status only contains Open or Closed",
        "warning",
        "SELECT count(*) FROM gold.dim_status WHERE request_status NOT IN ('Open', 'Closed')",
    ),
    Check(
        "freshness_days",
        "Days between the latest request in the data and the build date",
        "warning",
        "SELECT date_diff('day', max(created_at)::DATE, current_date) FROM gold.fact_service_request",
        threshold=14,
        unit="days",
    ),
    Check(
        "backlog_snapshot_reconciles",
        "Open service requests on the as-of date equal the sum of the latest backlog snapshot",
        "critical",
        """
        WITH latest_day AS (
            SELECT max(date_key) AS date_key FROM gold.fact_backlog_snapshot
        ),
        latest AS (
            SELECT sum(b.open_requests) AS snap, max(d.date) AS as_of
            FROM gold.fact_backlog_snapshot b
            JOIN latest_day USING (date_key)
            JOIN gold.dim_date d USING (date_key)
        ),
        actual AS (
            SELECT count(*) AS n FROM gold.fact_service_request f, latest l
            WHERE f.is_service_request
              AND f.created_at::DATE <= l.as_of
              AND (NOT f.is_closed OR coalesce(f.closed_at::DATE, f.created_at::DATE) > l.as_of)
        )
        SELECT abs(coalesce(snap, 0) - n) FROM latest, actual
        """,
    ),
    Check(
        "agg_reconciles_to_fact",
        "Daily aggregate row totals equal the fact row count",
        "critical",
        "SELECT abs((SELECT sum(requests) FROM gold.agg_daily_requests) - (SELECT count(*) FROM gold.fact_service_request))",
    ),
)


@dataclass(slots=True)
class CheckResult:
    name: str
    description: str
    severity: str
    value: float
    threshold: float
    unit: str
    passed: bool


def run_checks(con: duckdb.DuckDBPyConnection, checks: tuple[Check, ...] = CHECKS) -> list[CheckResult]:
    results: list[CheckResult] = []
    for c in checks:
        raw = con.execute(c.sql).fetchone()[0]
        value = float(raw) if raw is not None else 0.0
        results.append(
            CheckResult(
                name=c.name,
                description=c.description,
                severity=c.severity,
                value=value,
                threshold=c.threshold,
                unit=c.unit,
                passed=value <= c.threshold,
            )
        )
    return results


def summarize(results: list[CheckResult]) -> dict:
    critical_failures = [r.name for r in results if r.severity == "critical" and not r.passed]
    warnings = [r.name for r in results if r.severity == "warning" and not r.passed]
    return {
        "run_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "checks": len(results),
        "passed": sum(r.passed for r in results),
        "critical_failures": critical_failures,
        "warnings": warnings,
        "status": "FAIL" if critical_failures else ("WARN" if warnings else "PASS"),
        "results": [asdict(r) for r in results],
    }


def persist(con: duckdb.DuckDBPyConnection, report: dict) -> None:
    con.execute(
        """
        CREATE OR REPLACE TABLE meta.quality_results (
            run_at_utc VARCHAR, check_name VARCHAR, description VARCHAR, severity VARCHAR,
            value DOUBLE, threshold DOUBLE, unit VARCHAR, passed BOOLEAN
        )
        """
    )
    con.executemany(
        "INSERT INTO meta.quality_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                report["run_at_utc"],
                r["name"],
                r["description"],
                r["severity"],
                r["value"],
                r["threshold"],
                r["unit"],
                r["passed"],
            )
            for r in report["results"]
        ],
    )


def format_report(report: dict) -> str:
    lines = [f"Data quality: {report['status']}  ({report['passed']}/{report['checks']} checks passed)", ""]
    lines.append(f"{'check':34} {'severity':9} {'value':>12} {'threshold':>10}  result")
    for r in report["results"]:
        mark = "ok" if r["passed"] else ("FAIL" if r["severity"] == "critical" else "warn")
        lines.append(f"{r['name']:34} {r['severity']:9} {r['value']:>12g} {r['threshold']:>10g}  {mark}")
    return "\n".join(lines)


def run_quality(settings: Settings, report_path: Path | None = None) -> dict:
    con = connect(settings)
    try:
        results = run_checks(con)
        report = summarize(results)
        persist(con, report)
    finally:
        con.close()
    report_path = report_path or settings.warehouse_path.parent / "quality_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("Quality report written to %s", report_path)
    return report
