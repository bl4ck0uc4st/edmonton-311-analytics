-- Gold: daily aggregate by service area. A compact (~30k rows for 3 years) table for
-- quick trend charts, README statistics and sanity checks against the fact table.
CREATE OR REPLACE TABLE gold.agg_daily_requests AS
SELECT
    f.created_date_key                                                                   AS date_key,
    s.service_group,
    s.service_area,
    count(*)                                                                             AS requests,
    count(*) FILTER (WHERE f.is_service_request)                                         AS service_requests,
    count(*) FILTER (WHERE f.is_closed)                                                  AS closed_requests,
    count(*) FILTER (WHERE NOT f.is_closed)                                              AS still_open_requests,
    median(f.resolution_days) FILTER (WHERE f.is_service_request AND f.is_closed)        AS median_resolution_days,
    count(*) FILTER (WHERE f.sla_met)                                                    AS sla_met_count,
    count(*) FILTER (WHERE f.sla_met = FALSE)                                            AS sla_missed_count
FROM gold.fact_service_request f
JOIN gold.dim_service s USING (service_key)
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;
