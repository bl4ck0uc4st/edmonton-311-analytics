-- Q10. Year-over-year change by service group for the same months of each year (Jan..latest month).
WITH latest AS (
    SELECT max(month) AS last_month, max(year) AS last_year
    FROM gold.dim_date d JOIN gold.fact_service_request f ON f.created_date_key = d.date_key
),
ytd AS (
    SELECT d.year, s.service_group, count(*) AS requests
    FROM gold.fact_service_request f
    JOIN gold.dim_date d ON d.date_key = f.created_date_key
    JOIN gold.dim_service s USING (service_key)
    WHERE d.month <= (SELECT last_month FROM latest)
    GROUP BY 1, 2
)
SELECT
    service_group,
    year,
    requests,
    lag(requests) OVER (PARTITION BY service_group ORDER BY year)                     AS prior_year,
    round(100.0 * (requests - lag(requests) OVER (PARTITION BY service_group ORDER BY year))
          / nullif(lag(requests) OVER (PARTITION BY service_group ORDER BY year), 0), 1) AS yoy_pct
FROM ytd
ORDER BY service_group, year;
