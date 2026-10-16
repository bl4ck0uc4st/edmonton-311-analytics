-- Q9. What is still open right now, and how old is it?
SELECT
    s.service_group,
    f.backlog_age_bucket,
    count(*)                              AS open_requests,
    round(avg(f.open_age_days), 1)        AS avg_age_days,
    max(f.open_age_days)::INTEGER         AS oldest_days
FROM gold.fact_service_request f
JOIN gold.dim_service s USING (service_key)
WHERE NOT f.is_closed AND f.is_service_request
GROUP BY 1, 2
ORDER BY 1, CASE f.backlog_age_bucket WHEN '0-7 days' THEN 1 WHEN '8-30 days' THEN 2 WHEN '31-90 days' THEN 3 ELSE 4 END;
