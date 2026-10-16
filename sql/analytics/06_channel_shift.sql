-- Q6. Are residents moving from the phone to digital channels?
SELECT
    d.year_quarter,
    count(*)                                                                     AS requests,
    round(100.0 * count(*) FILTER (WHERE i.interaction_channel = 'Mobile App') / count(*), 1) AS mobile_app_pct,
    round(100.0 * count(*) FILTER (WHERE i.channel_group = 'Digital') / count(*), 1)          AS digital_pct,
    round(100.0 * count(*) FILTER (WHERE i.interaction_channel = 'Phone Call') / count(*), 1) AS phone_pct
FROM gold.fact_service_request f
JOIN gold.dim_date d ON d.date_key = f.created_date_key
JOIN gold.dim_intake i USING (intake_key)
GROUP BY 1
ORDER BY 1;
