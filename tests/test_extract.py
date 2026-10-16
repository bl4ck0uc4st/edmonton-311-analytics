from __future__ import annotations

import json
from datetime import date

import pyarrow.parquet as pq
import pytest
import requests

from yeg311.config import RAW_COLUMNS, Settings
from yeg311.extract import (
    MonthWindow,
    SodaClient,
    SodaRequestError,
    dataset_floor,
    month_windows,
    rows_to_table,
    run_extract,
    shift_months,
)


def test_month_windows_are_inclusive_and_ordered():
    windows = list(month_windows(date(2025, 11, 15), date(2026, 2, 3)))
    assert [w.label for w in windows] == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert windows[1].end == windows[2].start  # contiguous, exclusive upper bounds


def test_dataset_floor_is_two_calendar_years_back():
    assert dataset_floor(date(2026, 10, 15)) == date(2024, 1, 1)
    assert dataset_floor(date(2027, 1, 1)) == date(2025, 1, 1)


def test_shift_months_clamps_to_first_of_month():
    assert shift_months(date(2026, 10, 15), -2) == date(2026, 8, 1)
    assert shift_months(date(2026, 1, 31), -1) == date(2025, 12, 1)
    assert shift_months(date(2025, 12, 1), 1) == date(2026, 1, 1)


def test_rows_to_table_has_fixed_schema_and_handles_missing_keys():
    table = rows_to_table([{"row_id": "1", "date_created": "2026-01-01T00:00:00.000"}, {"row_id": "2"}])
    assert table.column_names == list(RAW_COLUMNS)
    assert table.num_rows == 2
    assert table.column("date_closed").null_count == 2
    assert rows_to_table([]).num_rows == 0


class _FakeResponse:
    def __init__(self, status: int, payload):
        self.status_code = status
        self._payload = payload
        self.text = str(payload)[:200]

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class _FakeSession:
    """Serves 120 rows for any month in 3 pages, failing the very first call with a 503."""

    def __init__(self, total_rows: int = 120, fail_first: bool = True):
        self.headers: dict[str, str] = {}
        self.calls: list[dict] = []
        self.total_rows = total_rows
        self._fail = fail_first

    def get(self, url, params=None, timeout=None):
        self.calls.append(dict(params))
        if "$offset" not in params:  # source summary query
            return _FakeResponse(
                200,
                [
                    {
                        "n": str(self.total_rows),
                        "min_dt": "2026-03-01T10:00:00.000",
                        "max_dt": "2026-03-01T10:00:00.000",
                    }
                ],
            )
        if self._fail:
            self._fail = False
            return _FakeResponse(503, {"error": "upstream"})
        offset, limit = int(params["$offset"]), int(params["$limit"])
        rows = [
            {"row_id": str(offset + i), "date_created": "2026-03-01T10:00:00.000", "request_status": "Open"}
            for i in range(min(limit, max(0, self.total_rows - offset)))
        ]
        return _FakeResponse(200, rows)


def test_client_paginates_and_retries(tmp_path, monkeypatch):
    monkeypatch.setattr("yeg311.extract.time.sleep", lambda *_: None)  # no pacing in tests
    settings = Settings(data_dir=tmp_path, page_size=50)
    session = _FakeSession()
    client = SodaClient(settings, session=session)  # type: ignore[arg-type]
    client.fetch_page.retry.sleep = lambda *_: None  # type: ignore[attr-defined]

    results = run_extract(settings, months=[MonthWindow(2026, 3)], client=client)

    assert results == {"2026-03": 120}
    page_calls = [c for c in session.calls if "$offset" in c]
    # 1 failed call + 3 pages (50 + 50 + 20)
    assert [c["$offset"] for c in page_calls] == ["0", "0", "50", "100"]
    assert "date_created >= '2026-03-01T00:00:00'" in page_calls[0]["$where"]
    part = settings.raw_dir / "year=2026" / "month=03" / "part-0.parquet"
    assert pq.read_table(part).num_rows == 120
    manifest = json.loads((settings.raw_dir / "_manifest.json").read_text())
    assert "2026-03" in manifest["partitions"]
    assert manifest["source"]["row_count"] == 120


def test_client_gives_up_after_retries(tmp_path, monkeypatch):
    class AlwaysDown(_FakeSession):
        def get(self, url, params=None, timeout=None):
            return _FakeResponse(500, {"error": "down"})

    settings = Settings(data_dir=tmp_path, page_size=50)
    client = SodaClient(settings, session=AlwaysDown())  # type: ignore[arg-type]
    client.fetch_page.retry.sleep = lambda *_: None  # type: ignore[attr-defined]
    with pytest.raises(SodaRequestError):
        client.fetch_page("date_created >= '2026-01-01'", 50, 0)


def test_incremental_mode_uses_lookback_window(tmp_path, monkeypatch):
    monkeypatch.setattr("yeg311.extract.time.sleep", lambda *_: None)
    settings = Settings(data_dir=tmp_path, page_size=500)
    settings.lookback_months = 2
    session = _FakeSession(total_rows=10, fail_first=False)
    client = SodaClient(settings, session=session)  # type: ignore[arg-type]
    results = run_extract(settings, mode="incremental", today=date(2026, 10, 15), client=client)
    assert list(results) == ["2026-09", "2026-10"]


def test_full_mode_discovers_source_floor(tmp_path, monkeypatch):
    monkeypatch.setattr("yeg311.extract.time.sleep", lambda *_: None)
    settings = Settings(data_dir=tmp_path, page_size=500)
    session = _FakeSession(total_rows=10, fail_first=False)
    client = SodaClient(settings, session=session)  # type: ignore[arg-type]
    results = run_extract(settings, mode="full", today=date(2026, 4, 15), client=client)
    # the API says data starts 2026-03-01, which is later than the assumed floor (2024-01-01):
    # the earliest of the two wins, so every month from the assumed floor is still extracted
    assert list(results)[0] == "2024-01"
    assert list(results)[-1] == "2026-04"


def test_full_mode_extends_window_when_source_is_older(tmp_path, monkeypatch):
    monkeypatch.setattr("yeg311.extract.time.sleep", lambda *_: None)

    class OldSource(_FakeSession):
        def get(self, url, params=None, timeout=None):
            if "$offset" not in params:
                return _FakeResponse(
                    200,
                    [{"n": "10", "min_dt": "2023-02-10T08:00:00.000", "max_dt": "2026-04-01T00:00:00.000"}],
                )
            return super().get(url, params=params, timeout=timeout)

    settings = Settings(data_dir=tmp_path, page_size=500)
    client = SodaClient(settings, session=OldSource(total_rows=10, fail_first=False))  # type: ignore[arg-type]
    results = run_extract(settings, mode="full", today=date(2026, 4, 15), client=client)
    assert list(results)[0] == "2023-02"
