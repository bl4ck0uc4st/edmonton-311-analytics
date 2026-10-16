-- Q4. End-of-month open backlog and how much of it is older than 30 days (periodic snapshot fact).
WITH month_end AS (
    SELECT year_month, max(date_key) AS date_key
    FROM gold.dim_date
    WHERE date_key IN (SELECT DISTINCT date_key FROM gold.fact_backlog_snapshot)
    GROUP BY 1
)
SELECT
    m.year_month,
    sum(b.open_requests)                                              AS open_requests,
    sum(b.open_over_30_days)                                          AS open_over_30_days,
    round(100.0 * sum(b.open_over_30_days) / nullif(sum(b.open_requests), 0), 1) AS pct_over_30_days
FROM month_end m
JOIN gold.fact_backlog_snapshot b USING (date_key)
GROUP BY 1
ORDER BY 1;
