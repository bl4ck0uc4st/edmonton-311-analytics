-- Q3. SLA attainment by business area (service requests only, illustrative targets).
SELECT
    s.service_area,
    count(*) FILTER (WHERE f.sla_met IS NOT NULL)                   AS evaluated,
    count(*) FILTER (WHERE f.sla_met)                               AS met,
    count(*) FILTER (WHERE f.sla_met = FALSE)                       AS missed,
    round(100.0 * count(*) FILTER (WHERE f.sla_met)
          / nullif(count(*) FILTER (WHERE f.sla_met IS NOT NULL), 0), 1) AS sla_met_pct,
    min(s.sla_target_days) || '-' || max(s.sla_target_days)         AS target_days_range
FROM gold.fact_service_request f
JOIN gold.dim_service s USING (service_key)
WHERE f.is_service_request
GROUP BY 1
HAVING count(*) FILTER (WHERE f.sla_met IS NOT NULL) >= 50
ORDER BY sla_met_pct;
