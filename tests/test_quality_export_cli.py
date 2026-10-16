from __future__ import annotations

import json
from datetime import date

import duckdb

from yeg311.cli import main
from yeg311.config import PROJECT_ROOT, Settings
from yeg311.export import export_gold
from yeg311.quality import CHECKS, Check, run_checks, run_quality, summarize
from yeg311.sample import generate_rows


def test_quality_passes_on_clean_build(settings: Settings, built_warehouse: dict):
    report = run_quality(settings)
    assert report["status"] in ("PASS", "WARN")
    assert report["critical_failures"] == []
    assert report["passed"] >= report["checks"] - 2
    assert (settings.warehouse_path.parent / "quality_report.json").exists()


def test_quality_detects_critical_failure(con: duckdb.DuckDBPyConnection):
    bad = Check("always_fails", "synthetic failing check", "critical", "SELECT 5")
    results = run_checks(con, (bad, *CHECKS[:2]))
    report = summarize(results)
    assert report["status"] == "FAIL"
    assert report["critical_failures"] == ["always_fails"]


def test_export_writes_parquet_csv_and_metadata(settings: Settings, built_warehouse: dict, tmp_path):
    out = tmp_path / "exports"
    meta = export_gold(settings, export_dir=out)
    for name in (
        "dim_date",
        "dim_service",
        "dim_neighbourhood",
        "dim_intake",
        "dim_status",
        "fact_service_request",
    ):
        assert (out / f"{name}.parquet").exists(), name
    assert (out / "dim_service.csv").exists()
    assert not (out / "fact_service_request.csv").exists()  # big table: parquet only
    assert (
        meta["files"]["fact_service_request"]["rows"]
        == built_warehouse["row_counts"]["gold.fact_service_request"]
    )
    parsed = json.loads((out / "metadata.json").read_text())
    assert parsed["build"]["pipeline_version"]


def test_sample_generator_is_deterministic_and_dirty():
    a = generate_rows(500, today=date(2026, 10, 15), seed=1)
    b = generate_rows(500, today=date(2026, 10, 15), seed=1)
    assert a == b
    ids = [r["row_id"] for r in a]
    assert len(ids) > len(set(ids))  # injected duplicates
    assert any(r["service_category"] in ("", None) for r in a)  # injected blanks
    assert any(r["request_status"] == "Open" for r in a)
    assert all(len(r["date_created"]) == 23 for r in a)  # Socrata floating timestamp format


def test_cli_end_to_end_on_sample(tmp_path):
    data_dir = tmp_path / "data"
    rc = main(["--data-dir", str(data_dir), "run", "--sample", "--rows", "1500", "--seed", "3"])
    assert rc == 0
    assert (data_dir / "exports" / "fact_service_request.parquet").exists()
    assert (data_dir / "warehouse" / "yeg311.duckdb").exists()
    rc = main(["--data-dir", str(data_dir), "stats"])
    assert rc == 0
    s = Settings(project_root=PROJECT_ROOT, data_dir=data_dir)
    assert s.export_dir == data_dir / "exports"


def test_charts_render(settings: Settings, built_warehouse: dict, tmp_path):
    from yeg311.charts import render_charts

    paths = render_charts(settings, out_dir=tmp_path / "charts")
    assert len(paths) == 6
    for p in paths:
        assert p.exists() and p.stat().st_size > 10_000, p.name
