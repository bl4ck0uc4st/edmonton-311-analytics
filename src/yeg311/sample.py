"""Synthetic sample generator.

Produces monthly bronze partitions with the *same shape and quirks* as the live
311 dataset so that the whole pipeline (silver cleaning, star schema, data quality
checks, exports, Power BI model) can be developed, demoed and tested offline and in CI
without hitting the API.

Realism that matters for the downstream logic:
* seasonality per category (snow in winter, potholes in spring, turf in summer),
* weekday / business-hour intake patterns,
* channel mix conditioned on whether the request was resolved at first contact
  ("Full Service") or referred to a business area ("Referral"),
* right-skewed resolution times (log-normal) that leave a realistic open backlog,
* a sprinkle of genuine data-quality defects (duplicates, blank categories, padded
  whitespace, a few closed-before-created timestamps) so the quality checks have
  something to catch. Everything here is clearly synthetic and not City of Edmonton data.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import numpy as np
import pyarrow as pa

from .config import RAW_COLUMNS, Settings
from .extract import RAW_SCHEMA, MonthWindow, dataset_floor, month_windows, save_manifest, write_partition
from .sample_vocab import (
    CHANNELS_FULL_SERVICE,
    CHANNELS_REFERRAL,
    NEIGHBOURHOODS,
    SEASON_PROFILE,
    SERVICE_VOCAB,
    STATUS_DETAILS_CLOSED,
    STATUS_DETAILS_OPEN,
    WARDS,
)

log = logging.getLogger(__name__)

_HOUR_WEIGHTS = np.array(
    [
        0.2,
        0.1,
        0.1,
        0.1,
        0.1,
        0.2,
        0.6,
        1.4,
        2.6,
        3.2,
        3.2,
        3.0,
        2.8,
        3.0,
        3.0,
        2.8,
        2.4,
        1.8,
        1.2,
        0.9,
        0.7,
        0.5,
        0.4,
        0.3,
    ],
    dtype=float,
)
_DOW_WEIGHTS = np.array([1.35, 1.25, 1.2, 1.15, 1.05, 0.45, 0.35], dtype=float)  # Mon..Sun


def _choice(rng: np.random.Generator, items: list, weights: list[float], n: int) -> np.ndarray:
    w = np.asarray(weights, dtype=float)
    w = w / w.sum()
    idx = rng.choice(len(items), size=n, p=w)
    return idx


def _fmt_ts(ts: datetime) -> str:
    """Socrata floating timestamp format, e.g. 2026-10-13T23:57:42.000"""
    return ts.strftime("%Y-%m-%dT%H:%M:%S.000")


def generate_rows(
    n_rows: int, today: date, seed: int = 42, start: date | None = None
) -> list[dict[str, str | None]]:
    """Generate ``n_rows`` synthetic raw records spanning ``start``..``today``."""
    rng = np.random.default_rng(seed)
    start = start or dataset_floor(today)
    n_days = (today - start).days + 1

    # --- service type -----------------------------------------------------------
    svc_weights = [v[3] for v in SERVICE_VOCAB]
    svc_idx = _choice(rng, SERVICE_VOCAB, svc_weights, n_rows)

    # --- created timestamp: day drawn with seasonal x weekday weights per service ---
    day_offsets = np.arange(n_days)
    day_dates = [start + timedelta(days=int(d)) for d in day_offsets]
    month_of_day = np.array([d.month - 1 for d in day_dates])
    dow_of_day = np.array([d.weekday() for d in day_dates])
    growth = np.linspace(0.9, 1.1, n_days)  # mild year-over-year growth
    base_day_w = _DOW_WEIGHTS[dow_of_day] * growth

    season_names = sorted(SEASON_PROFILE)
    day_weights_by_season = {s: base_day_w * np.array(SEASON_PROFILE[s])[month_of_day] for s in season_names}
    for s in season_names:
        day_weights_by_season[s] = day_weights_by_season[s] / day_weights_by_season[s].sum()

    chosen_day = np.empty(n_rows, dtype=int)
    svc_seasons = np.array([SERVICE_VOCAB[i][7] for i in svc_idx])
    for s in season_names:
        mask = svc_seasons == s
        k = int(mask.sum())
        if k:
            chosen_day[mask] = rng.choice(n_days, size=k, p=day_weights_by_season[s])

    hours = rng.choice(24, size=n_rows, p=_HOUR_WEIGHTS / _HOUR_WEIGHTS.sum())
    minutes = rng.integers(0, 60, size=n_rows)
    seconds = rng.integers(0, 60, size=n_rows)
    created = [
        datetime.combine(day_dates[d], datetime.min.time())
        + timedelta(hours=int(h), minutes=int(m), seconds=int(s))
        for d, h, m, s in zip(chosen_day, hours, minutes, seconds, strict=True)
    ]
    now = datetime.combine(today, datetime.min.time()) + timedelta(hours=12)
    created = [min(c, now - timedelta(minutes=1)) for c in created]

    # --- resolution: log-normal around the category median; open if not yet closed ---
    medians = np.array([SERVICE_VOCAB[i][5] for i in svc_idx], dtype=float)
    sigma = np.where(medians < 1, 0.9, 0.75)
    res_days = np.exp(np.log(np.maximum(medians, 0.0005)) + sigma * rng.standard_normal(n_rows))
    res_days = np.minimum(res_days, 400.0)

    rows: list[dict[str, str | None]] = []
    referral_types = [SERVICE_VOCAB[i][4] for i in svc_idx]
    nbhd_probs = np.array([SERVICE_VOCAB[i][6] for i in svc_idx])
    nbhd_draw = rng.random(n_rows) < nbhd_probs
    nbhd_pick = rng.integers(0, len(NEIGHBOURHOODS), size=n_rows)
    ids_base = rng.integers(10**12, 6 * 10**13, size=n_rows, dtype=np.int64)
    u_detail = rng.random(n_rows)
    u_channel = rng.random(n_rows)
    u_ref_blank = rng.random(n_rows)

    cl_items = [d for d, _ in STATUS_DETAILS_CLOSED]
    cl_cum = np.cumsum([w for _, w in STATUS_DETAILS_CLOSED]) / sum(w for _, w in STATUS_DETAILS_CLOSED)
    op_items = [d for d, _ in STATUS_DETAILS_OPEN]
    op_cum = np.cumsum([w for _, w in STATUS_DETAILS_OPEN]) / sum(w for _, w in STATUS_DETAILS_OPEN)
    fs_items = [c for c, _ in CHANNELS_FULL_SERVICE]
    fs_cum = np.cumsum([w for _, w in CHANNELS_FULL_SERVICE]) / sum(w for _, w in CHANNELS_FULL_SERVICE)
    rf_items = [c for c, _ in CHANNELS_REFERRAL]
    rf_cum = np.cumsum([w for _, w in CHANNELS_REFERRAL]) / sum(w for _, w in CHANNELS_REFERRAL)

    for i in range(n_rows):
        area, category, description, _w, _ref, _med, _np, _season = SERVICE_VOCAB[svc_idx[i]]
        c = created[i]
        closed_at = c + timedelta(days=float(res_days[i]))
        is_closed = closed_at <= now
        referral = referral_types[i]
        if u_ref_blank[i] < 0.007:
            referral = None  # the source occasionally omits referral_type
        if referral == "Full Service" or referral is None:
            channel = fs_items[int(np.searchsorted(fs_cum, u_channel[i]))]
        else:
            channel = rf_items[int(np.searchsorted(rf_cum, u_channel[i]))]
        if is_closed:
            detail = cl_items[int(np.searchsorted(cl_cum, u_detail[i]))]
        else:
            detail = op_items[int(np.searchsorted(op_cum, u_detail[i]))]

        row: dict[str, str | None] = {
            "row_id": str(int(ids_base[i])),
            "date_created": _fmt_ts(c),
            "date_closed": _fmt_ts(closed_at) if is_closed else None,
            "request_status": "Closed" if is_closed else "Open",
            "status_detail": detail,
            "service_area": area,
            "service_category": category,
            "service_description": description,
            "interaction_channel": channel,
            "referral_type": referral,
            "neighbourhood_id": None,
            "neighbourhood": None,
            "ward": None,
            "nbhd_latitude": None,
            "nbhd_longitude": None,
            "ward_latitude": None,
            "ward_longitude": None,
        }
        if nbhd_draw[i]:
            nid, nname, ward, lat, lon = NEIGHBOURHOODS[nbhd_pick[i]]
            wlat, wlon = WARDS[ward]
            row.update(
                {
                    "neighbourhood_id": nid,
                    "neighbourhood": nname,
                    "ward": ward,
                    "nbhd_latitude": f"{lat:.13f}",
                    "nbhd_longitude": f"{lon:.12f}",
                    "ward_latitude": f"{wlat:.13f}",
                    "ward_longitude": f"{wlon:.12f}",
                }
            )
        rows.append(row)

    _inject_defects(rows, rng)
    return rows


def _inject_defects(rows: list[dict[str, str | None]], rng: np.random.Generator) -> None:
    """Add a small, realistic amount of dirt. Rates are per-row probabilities."""
    n = len(rows)
    # 1) exact duplicate re-publications (~0.1%), some of them with a newer close date
    dup_idx = rng.choice(n, size=max(1, n // 1000), replace=False)
    for i in dup_idx:
        dup = dict(rows[i])
        if dup["date_closed"] is None and rng.random() < 0.5:
            closed = datetime.strptime(dup["date_created"], "%Y-%m-%dT%H:%M:%S.000") + timedelta(days=3)
            dup["date_closed"] = _fmt_ts(closed)
            dup["request_status"] = "Closed"
        rows.append(dup)
    # 2) closed-before-created timestamps (~0.02%)
    for i in rng.choice(n, size=max(1, n // 5000), replace=False):
        if rows[i]["date_closed"]:
            created = datetime.strptime(rows[i]["date_created"], "%Y-%m-%dT%H:%M:%S.000")
            rows[i]["date_closed"] = _fmt_ts(created - timedelta(hours=2))
    # 3) blank service classification (~0.1%)
    for i in rng.choice(n, size=max(1, n // 1000), replace=False):
        rows[i]["service_area"] = None
        rows[i]["service_category"] = ""
        rows[i]["service_description"] = None
    # 4) padded whitespace in a text field (~0.2%)
    for i in rng.choice(n, size=max(1, n // 500), replace=False):
        if rows[i]["service_category"]:
            rows[i]["service_category"] = f" {rows[i]['service_category']} "


def rows_to_table(rows: list[dict[str, str | None]]) -> pa.Table:
    cols = {c: [r.get(c) for r in rows] for c in RAW_COLUMNS}
    return pa.Table.from_arrays([pa.array(cols[c], type=pa.string()) for c in RAW_COLUMNS], schema=RAW_SCHEMA)


def write_sample(
    settings: Settings, n_rows: int = 25_000, seed: int = 42, today: date | None = None
) -> dict[str, int]:
    """Generate synthetic data and write it as monthly bronze partitions + manifest."""
    today = today or date.today()
    rows = generate_rows(n_rows, today=today, seed=seed)
    by_month: dict[tuple[int, int], list[dict[str, str | None]]] = {}
    for r in rows:
        key = (int(r["date_created"][0:4]), int(r["date_created"][5:7]))  # type: ignore[index]
        by_month.setdefault(key, []).append(r)

    manifest = {"dataset_id": "SYNTHETIC-SAMPLE", "seed": seed, "partitions": {}}
    counts: dict[str, int] = {}
    for window in month_windows(dataset_floor(today), today):
        month_rows = by_month.get((window.year, window.month), [])
        write_partition(rows_to_table(month_rows), window.partition_dir(settings.raw_dir))
        counts[window.label] = len(month_rows)
        manifest["partitions"][window.label] = {"rows": len(month_rows), "extracted_at": "synthetic"}
    save_manifest(settings.raw_dir, manifest)
    log.info("Wrote synthetic sample: %s rows across %s months", f"{len(rows):,}", len(counts))
    return counts


__all__ = ["generate_rows", "write_sample", "MonthWindow"]
