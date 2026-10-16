-- Q7. When do requests arrive? Weekday x hour-of-day intake profile (pivot in Power BI as a matrix).
SELECT
    d.day_name,
    d.day_of_week,
    f.created_hour,
    count(*) AS requests
FROM gold.fact_service_request f
JOIN gold.dim_date d ON d.date_key = f.created_date_key
GROUP BY 1, 2, 3
ORDER BY d.day_of_week, f.created_hour;
