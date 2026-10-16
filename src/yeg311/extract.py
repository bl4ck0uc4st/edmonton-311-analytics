"""Extract layer: City of Edmonton 311 Requests -> monthly Parquet partitions (bronze).

Design notes
------------
* The source is a Socrata (SODA 2.1) dataset of ~3.5 million rows covering a rolling
  window of the current calendar year plus the two previous years.
* We pull the data **one calendar month at a time** (``$where date_created >= ... AND
  date_created < ...``) and page through each month with ``$limit/$offset`` ordered by
  a deterministic key. Each month lands in its own hive-style partition
  (``year=YYYY/month=MM/part-0.parquet``), which gives us:

    - a natural unit of incremental work (re-extract only the last N months),
    - resumability (a failed run leaves earlier months intact),
    - fast partition pruning in DuckDB.

* Requests change status after creation (Open -> Closed), so an incremental run
  re-extracts a *lookback window* of recent months rather than only new rows. A
  periodic full refresh (weekly in CI) catches long-lived requests outside the window.
* Raw values are stored exactly as received (all columns as strings). Typing and
  cleaning are the silver layer's job; the bronze layer is an auditable copy of the API.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import DATASET_URL, RAW_COLUMNS, Settings

log = logging.getLogger(__name__)

RAW_SCHEMA = pa.schema([pa.field(c, pa.string()) for c in RAW_COLUMNS])


class SodaRequestError(RuntimeError):
    """Raised for HTTP errors we are willing to retry (5xx, 429, timeouts)."""


@dataclass(frozen=True, slots=True)
class MonthWindow:
    year: int
    month: int

    @property
    def start(self) -> datetime:
        return datetime(self.year, self.month, 1)

    @property
    def end(self) -> datetime:
        """Exclusive upper bound: first instant of the following month."""
        if self.month == 12:
            return datetime(self.year + 1, 1, 1)
        return datetime(self.year, self.month + 1, 1)

    @property
    def label(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    def partition_dir(self, raw_dir: Path) -> Path:
        return raw_dir / f"year={self.year:04d}" / f"month={self.month:02d}"


def month_windows(start: date, end: date) -> Iterator[MonthWindow]:
    """Yield every calendar month from ``start``'s month to ``end``'s month inclusive."""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield MonthWindow(y, m)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def dataset_floor(today: date) -> date:
    """The portal keeps the current year plus the previous two calendar years."""
    return date(today.year - 2, 1, 1)


def shift_months(d: date, months: int) -> date:
    """Move ``d`` back/forward by ``months`` whole months, clamped to the 1st of the month."""
    idx = d.year * 12 + (d.month - 1) + months
    return date(idx // 12, idx % 12 + 1, 1)


class SodaClient:
    """Minimal, dependency-light SODA client with retries and polite pacing."""

    def __init__(
        self,
        settings: Settings,
        session: requests.Session | None = None,
        base_url: str = DATASET_URL,
        pause_s: float = 0.2,
    ) -> None:
        self.settings = settings
        self.session = session or requests.Session()
        self.base_url = base_url
        self.pause_s = pause_s
        self.session.headers.update({"Accept": "application/json", "User-Agent": "yeg311-pipeline/1.0"})
        if settings.app_token:
            # An app token moves us out of the shared anonymous throttling pool.
            self.session.headers["X-App-Token"] = settings.app_token

    # -- single page ---------------------------------------------------------------
    @retry(
        reraise=True,
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=1.5, min=2, max=60),
        retry=retry_if_exception_type((SodaRequestError, requests.ConnectionError, requests.Timeout)),
    )
    def fetch_page(self, where: str, limit: int, offset: int) -> list[dict[str, str]]:
        params = {
            "$select": ",".join(RAW_COLUMNS),
            "$where": where,
            "$order": "date_created, row_id",
            "$limit": str(limit),
            "$offset": str(offset),
        }
        resp = self.session.get(self.base_url, params=params, timeout=self.settings.request_timeout_s)
        if resp.status_code == 429 or resp.status_code >= 500:
            raise SodaRequestError(f"HTTP {resp.status_code} for offset={offset}: {resp.text[:200]}")
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, list):
            raise SodaRequestError(f"Unexpected payload type {type(payload).__name__}")
        return payload

    # -- source summary -----------------------------------------------------------------
    @retry(
        reraise=True,
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=1.5, min=2, max=60),
        retry=retry_if_exception_type((SodaRequestError, requests.ConnectionError, requests.Timeout)),
    )
    def fetch_source_summary(self) -> dict[str, str | None]:
        """Row count and creation-date range as the API reports them right now.

        Used to (a) discover the real extent of the rolling window instead of assuming it and
        (b) reconcile the number of rows we landed against the source after a full run.
        """
        params = {"$select": "count(*) AS n, min(date_created) AS min_dt, max(date_created) AS max_dt"}
        resp = self.session.get(self.base_url, params=params, timeout=self.settings.request_timeout_s)
        if resp.status_code == 429 or resp.status_code >= 500:
            raise SodaRequestError(f"HTTP {resp.status_code} for source summary: {resp.text[:200]}")
        resp.raise_for_status()
        payload = resp.json()
        row = payload[0] if isinstance(payload, list) and payload else {}
        return {"n": row.get("n"), "min_dt": row.get("min_dt"), "max_dt": row.get("max_dt")}

    # -- whole month ----------------------------------------------------------------
    def iter_month(self, window: MonthWindow) -> Iterator[list[dict[str, str]]]:
        where = f"date_created >= '{window.start.isoformat()}' AND date_created < '{window.end.isoformat()}'"
        offset = 0
        while True:
            page = self.fetch_page(where, self.settings.page_size, offset)
            if not page:
                return
            yield page
            if len(page) < self.settings.page_size:
                return
            offset += self.settings.page_size
            time.sleep(self.pause_s)


def rows_to_table(rows: Iterable[dict[str, str]]) -> pa.Table:
    """Build a pyarrow table with a fixed, all-string schema (missing keys -> null)."""
    columns: dict[str, list[str | None]] = {c: [] for c in RAW_COLUMNS}
    n = 0
    for row in rows:
        n += 1
        for c in RAW_COLUMNS:
            v = row.get(c)
            columns[c].append(None if v is None else str(v))
    arrays = [pa.array(columns[c], type=pa.string()) for c in RAW_COLUMNS]
    return pa.Table.from_arrays(arrays, schema=RAW_SCHEMA) if n else RAW_SCHEMA.empty_table()


def write_partition(table: pa.Table, part_dir: Path) -> Path:
    """Write ``part-0.parquet`` atomically (temp file + rename) so readers never see a torn file."""
    part_dir.mkdir(parents=True, exist_ok=True)
    final = part_dir / "part-0.parquet"
    tmp = part_dir / "part-0.parquet.tmp"
    pq.write_table(table, tmp, compression="zstd")
    tmp.replace(final)
    return final


def load_manifest(raw_dir: Path) -> dict:
    path = raw_dir / "_manifest.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"dataset_id": DATASET_URL, "partitions": {}}


def save_manifest(raw_dir: Path, manifest: dict) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def extract_month(client: SodaClient, window: MonthWindow, settings: Settings) -> int:
    """Download one month into its partition. Returns the number of rows written."""
    tables: list[pa.Table] = []
    total = 0
    for page in client.iter_month(window):
        t = rows_to_table(page)
        total += t.num_rows
        tables.append(t)
        log.info("  %s: %s rows so far", window.label, f"{total:,}")
    table = pa.concat_tables(tables) if tables else RAW_SCHEMA.empty_table()
    write_partition(table, window.partition_dir(settings.raw_dir))
    return total


def run_extract(
    settings: Settings,
    mode: str = "incremental",
    today: date | None = None,
    client: SodaClient | None = None,
    months: Iterable[MonthWindow] | None = None,
) -> dict[str, int]:
    """Extract either every month in the dataset window (``full``) or the lookback window."""
    today = today or date.today()
    client = client or SodaClient(settings)
    manifest = load_manifest(settings.raw_dir)

    source: dict[str, str | None] = {}
    try:
        source = client.fetch_source_summary()
        log.info(
            "Source reports %s rows, created %s .. %s",
            source.get("n"),
            source.get("min_dt"),
            source.get("max_dt"),
        )
    except Exception as exc:  # the summary is a nice-to-have; never block extraction on it
        log.warning("Could not read the source summary (%s); falling back to the assumed window", exc)

    if months is None:
        if mode == "full":
            # Trust the API's own minimum creation date over the documented rolling window: the
            # portal trims old years on its own schedule, so the real floor moves.
            start = dataset_floor(today)
            if source.get("min_dt"):
                start = min(start, date.fromisoformat(str(source["min_dt"])[:10]))
        elif mode == "incremental":
            start = shift_months(today, -(settings.lookback_months - 1))
        else:
            raise ValueError(f"unknown mode {mode!r}; expected 'full' or 'incremental'")
        end = today
        if source.get("max_dt"):
            end = max(end, date.fromisoformat(str(source["max_dt"])[:10]))
        months = list(month_windows(start, end))

    if source:
        manifest["source"] = {
            "row_count": int(source["n"]) if source.get("n") else None,
            "min_created": source.get("min_dt"),
            "max_created": source.get("max_dt"),
            "queried_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    results: dict[str, int] = {}
    for window in months:
        log.info("Extracting %s ...", window.label)
        n = extract_month(client, window, settings)
        results[window.label] = n
        manifest["partitions"][window.label] = {
            "rows": n,
            "extracted_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        save_manifest(settings.raw_dir, manifest)
        log.info("Done %s: %s rows", window.label, f"{n:,}")

    landed = sum(int(p["rows"]) for p in manifest["partitions"].values())
    expected = (manifest.get("source") or {}).get("row_count")
    if mode == "full" and expected:
        gap = expected - landed
        if abs(gap) > max(1000, expected * 0.005):
            log.warning(
                "Row count reconciliation: source reports %s rows but partitions hold %s (gap %s)",
                f"{expected:,}",
                f"{landed:,}",
                f"{gap:+,}",
            )
        else:
            log.info("Row count reconciliation OK: source %s vs landed %s", f"{expected:,}", f"{landed:,}")
    return results
