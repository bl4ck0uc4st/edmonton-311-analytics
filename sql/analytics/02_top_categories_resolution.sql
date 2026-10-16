-- Q2. Which request types create the most work, and how long do they take?
SELECT
    s.service_group,
    s.service_category,
    count(*)                                                    AS service_requests,
    round(median(f.resolution_days) FILTER (WHERE f.is_closed), 1)       AS median_days,
    round(quantile_cont(f.resolution_days, 0.9) FILTER (WHERE f.is_closed), 1) AS p90_days,
    round(100.0 * count(*) FILTER (WHERE f.sla_met) / nullif(count(*) FILTER (WHERE f.sla_met IS NOT NULL), 0), 1) AS sla_met_pct
FROM gold.fact_service_request f
JOIN gold.dim_service s USING (service_key)
WHERE f.is_service_request
GROUP BY 1, 2
ORDER BY service_requests DESC
LIMIT 15;
