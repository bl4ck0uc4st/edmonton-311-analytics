from __future__ import annotations

import duckdb

from tests.conftest import PINNED_TODAY


def test_build_summary_counts(built_warehouse: dict):
    rc = built_warehouse["row_counts"]
    assert rc["gold.fact_service_request"] == rc["silver.requests"]
    assert rc["gold.fact_service_request"] >= 5_900  # 6,000 generated minus nothing (duplicates removed)
    assert rc["gold.dim_intake"] >= 5
    assert built_warehouse["as_of"].startswith(str(PINNED_TODAY))


def test_duplicates_are_collapsed(con: duckdb.DuckDBPyConnection):
    bronze = con.execute("SELECT count(*), count(DISTINCT row_id) FROM bronze.requests").fetchone()
    assert bronze[0] > bronze[1], "the synthetic sample should contain duplicate row_ids"
    silver = con.execute("SELECT count(*), count(DISTINCT request_id_raw) FROM silver.requests").fetchone()
    assert silver[0] == silver[1] == bronze[1]


def test_whitespace_is_normalised(con: duckdb.DuckDBPyConnection):
    bad = con.execute(
        r"""
        SELECT count(*) FROM gold.dim_service
        WHERE service_category LIKE '% %' AND service_category <> trim(service_category)
           OR regexp_matches(service_category, '\s{2,}')
           OR regexp_matches(service_area, '\s{2,}')
        """
    ).fetchone()[0]
    assert bad == 0
    categories = {
        r[0] for r in con.execute("SELECT DISTINCT service_category FROM gold.dim_service").fetchall()
    }
    assert "Maintenance - Snow and Ice" in categories
    assert not any("  " in c for c in categories)


def test_closed_before_created_is_rejected_but_flagged(con: duckdb.DuckDBPyConnection):
    flagged = con.execute("SELECT count(*) FROM silver.requests WHERE closed_before_created_flag").fetchone()[
        0
    ]
    assert flagged > 0
    assert (
        con.execute("SELECT count(*) FROM gold.fact_service_request WHERE resolution_hours < 0").fetchone()[0]
        == 0
    )
    assert (
        con.execute(
            "SELECT count(*) FROM gold.fact_service_request WHERE closed_before_created_flag AND closed_at IS NOT NULL"
        ).fetchone()[0]
        == 0
    )


def test_unclassified_rows_get_explicit_members(con: duckdb.DuckDBPyConnection):
    assert (
        con.execute("SELECT count(*) FROM gold.dim_service WHERE service_area = 'Unclassified'").fetchone()[0]
        == 1
    )
    unknown_nbhd = con.execute(
        "SELECT count(*) FROM gold.fact_service_request WHERE neighbourhood_key = -1"
    ).fetchone()[0]
    assert unknown_nbhd > 0
    assert con.execute(
        "SELECT is_unknown_member FROM gold.dim_neighbourhood WHERE neighbourhood_key = -1"
    ).fetchone()[0]


def test_sla_precedence(con: duckdb.DuckDBPyConnection):
    rows = dict(
        con.execute(
            """
            SELECT service_category, max(sla_target_days) FROM gold.dim_service
            WHERE service_area = 'Roadway Maintenance' GROUP BY 1
            """
        ).fetchall()
    )
    assert rows["Potholes"] == 30  # exact (area, category) match
    assert rows["Maintenance - Snow and Ice"] == 10  # whitespace-normalised category still matches the seed
    assert rows["Maintenance - Open Space Structures"] == 30  # (area, any) default
    rec = con.execute(
        "SELECT sla_basis FROM gold.dim_service WHERE service_area = 'Recreation and Leisure Centres' LIMIT 1"
    ).fetchone()[0]
    assert rec.startswith("Global default")


def test_sla_only_evaluated_for_service_requests(con: duckdb.DuckDBPyConnection):
    assert (
        con.execute(
            "SELECT count(*) FROM gold.fact_service_request WHERE sla_met IS NOT NULL AND NOT is_service_request"
        ).fetchone()[0]
        == 0
    )
    assert (
        con.execute(
            "SELECT count(*) FROM gold.fact_service_request WHERE sla_met IS NOT NULL AND NOT is_closed"
        ).fetchone()[0]
        == 0
    )


def test_date_dimension(con: duckdb.DuckDBPyConnection):
    first, last, n = con.execute("SELECT min(date), max(date), count(*) FROM gold.dim_date").fetchone()
    assert str(first) == "2024-01-01"
    assert str(last) == "2027-12-31"
    assert n == 1461  # 2024 leap year + 2025 + 2026 + 2027
    holidays = con.execute("SELECT count(*) FROM gold.dim_date WHERE is_holiday").fetchone()[0]
    assert holidays >= 36  # at least 9 Alberta statutory holidays per year
    assert (
        con.execute("SELECT holiday_name FROM gold.dim_date WHERE date = DATE '2026-07-01'").fetchone()[0]
        == "Canada Day"
    )
    assert (
        con.execute("SELECT season FROM gold.dim_date WHERE date = DATE '2026-01-15'").fetchone()[0]
        == "Winter"
    )


def test_neighbourhood_title_case(con: duckdb.DuckDBPyConnection):
    names = {r[0] for r in con.execute("SELECT neighbourhood_name FROM gold.dim_neighbourhood").fetchall()}
    assert "Downtown" in names
    assert "McCauley" in names
    assert "Queen Alexandra" in names


def test_backlog_snapshot_matches_point_in_time_count(con: duckdb.DuckDBPyConnection):
    """The snapshot for an arbitrary past day must equal an event-in-progress count on that day."""
    day = "2026-05-15"
    snap = con.execute(
        "SELECT sum(open_requests) FROM gold.fact_backlog_snapshot WHERE date_key = 20260515"
    ).fetchone()[0]
    direct = con.execute(
        f"""
        SELECT count(*) FROM gold.fact_service_request
        WHERE is_service_request
          AND created_at::DATE <= DATE '{day}'
          AND (NOT is_closed OR coalesce(closed_at::DATE, created_at::DATE) > DATE '{day}')
        """
    ).fetchone()[0]
    assert snap == direct


def test_fact_keys_resolve(con: duckdb.DuckDBPyConnection):
    for dim, key in [
        ("gold.dim_service", "service_key"),
        ("gold.dim_neighbourhood", "neighbourhood_key"),
        ("gold.dim_intake", "intake_key"),
        ("gold.dim_status", "status_key"),
    ]:
        orphans = con.execute(
            f"SELECT count(*) FROM gold.fact_service_request f LEFT JOIN {dim} d USING ({key}) WHERE d.{key} IS NULL"
        ).fetchone()[0]
        assert orphans == 0, f"orphan keys in {dim}"
