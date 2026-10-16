"""Headline statistics from the warehouse, for the README and quick sanity checks."""

from __future__ import annotations

from .config import Settings
from .warehouse import connect

HEADLINE_SQL = """
WITH f AS (
    SELECT f.*, d.service_group, d.service_area, d.service_category, i.interaction_channel
    FROM gold.fact_service_request f
    JOIN gold.dim_service d USING (service_key)
    JOIN gold.dim_intake i USING (intake_key)
)
SELECT
    count(*)                                                                     AS total_requests,
    count(*) FILTER (WHERE is_service_request)                                   AS service_requests,
    count(*) FILTER (WHERE NOT is_closed AND is_service_request)                 AS open_service_requests,
    round(100.0 * count(*) FILTER (WHERE sla_met) / nullif(count(*) FILTER (WHERE sla_met IS NOT NULL), 0), 1) AS sla_met_pct,
    round(median(resolution_days) FILTER (WHERE is_service_request AND is_closed), 1) AS median_resolution_days_sr,
    round(100.0 * count(*) FILTER (WHERE interaction_channel = 'Mobile App') / count(*), 1) AS mobile_app_share_pct,
    min(created_at)::DATE                                                        AS first_request,
    max(created_at)::DATE                                                        AS last_request
FROM f
"""

TOP_CATEGORIES_SQL = """
SELECT d.service_category, d.service_area, count(*) AS requests,
       round(median(f.resolution_days) FILTER (WHERE f.is_closed AND f.is_service_request), 1) AS median_days
FROM gold.fact_service_request f JOIN gold.dim_service d USING (service_key)
WHERE f.is_service_request
GROUP BY 1, 2 ORDER BY requests DESC LIMIT 10
"""

MONTHLY_SQL = """
SELECT d.year_month, count(*) AS requests,
       count(*) FILTER (WHERE f.is_service_request) AS service_requests
FROM gold.fact_service_request f JOIN gold.dim_date d ON d.date_key = f.created_date_key
GROUP BY 1 ORDER BY 1
"""


def headline_stats(settings: Settings) -> dict:
    con = connect(settings, read_only=True)
    try:
        cols = [c[0] for c in con.execute(HEADLINE_SQL).description]
        row = con.execute(HEADLINE_SQL).fetchone()
        head = dict(zip(cols, row, strict=True))
        top = con.execute(TOP_CATEGORIES_SQL).fetchall()
        monthly = con.execute(MONTHLY_SQL).fetchall()
    finally:
        con.close()
    return {"headline": head, "top_categories": top, "monthly": monthly}


def format_stats(stats: dict) -> str:
    h = stats["headline"]
    out = [
        "Headline numbers",
        f"  Requests in data            : {h['total_requests']:,}  ({h['first_request']} to {h['last_request']})",
        f"  Service requests (referred) : {h['service_requests']:,}",
        f"  Open service requests       : {h['open_service_requests']:,}",
        f"  SLA met (illustrative)      : {h['sla_met_pct']}%",
        f"  Median resolution (SR)      : {h['median_resolution_days_sr']} days",
        f"  Mobile App share            : {h['mobile_app_share_pct']}%",
        "",
        "Top service-request categories",
    ]
    for cat, area, n, med in stats["top_categories"]:
        out.append(f"  {n:>9,}  {cat} ({area})  median {med} days")
    out.append("")
    out.append("Monthly volume")
    for ym, n, sr in stats["monthly"]:
        out.append(f"  {ym}  {n:>9,} total  {sr:>9,} service requests")
    return "\n".join(out)
