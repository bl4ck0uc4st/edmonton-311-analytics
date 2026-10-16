-- Q1. How is monthly demand trending, and what share gets closed?
SELECT
    d.year_month,
    count(*)                                                         AS requests,
    count(*) FILTER (WHERE f.is_service_request)                     AS service_requests,
    round(100.0 * count(*) FILTER (WHERE f.is_closed) / count(*), 1) AS closure_rate_pct,
    round(100.0 * (count(*) - lag(count(*)) OVER (ORDER BY d.year_month))
          / nullif(lag(count(*)) OVER (ORDER BY d.year_month), 0), 1) AS mom_change_pct
FROM gold.fact_service_request f
JOIN gold.dim_date d ON d.date_key = f.created_date_key
GROUP BY 1
ORDER BY 1;
