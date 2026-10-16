-- Q8. Do statutory holidays and weekends change daily demand?
WITH daily AS (
    SELECT d.date, d.day_type, count(f.request_id) AS requests
    FROM gold.dim_date d
    LEFT JOIN gold.fact_service_request f ON f.created_date_key = d.date_key
    WHERE d.date BETWEEN (SELECT min(created_at)::DATE FROM gold.fact_service_request)
                     AND (SELECT max(created_at)::DATE FROM gold.fact_service_request)
    GROUP BY 1, 2
)
SELECT day_type, count(*) AS days, round(avg(requests), 1) AS avg_requests_per_day,
       round(median(requests), 1) AS median_requests_per_day
FROM daily
GROUP BY 1
ORDER BY avg_requests_per_day DESC;
