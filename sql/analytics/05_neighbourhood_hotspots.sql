-- Q5. Which neighbourhoods generate the most service requests, and what do they ask for most?
WITH per_nbhd AS (
    SELECT n.neighbourhood_name, n.ward, s.service_category, count(*) AS n
    FROM gold.fact_service_request f
    JOIN gold.dim_neighbourhood n USING (neighbourhood_key)
    JOIN gold.dim_service s USING (service_key)
    WHERE f.is_service_request AND NOT n.is_unknown_member
    GROUP BY 1, 2, 3
),
ranked AS (
    SELECT *,
           sum(n) OVER (PARTITION BY neighbourhood_name)                              AS total,
           row_number() OVER (PARTITION BY neighbourhood_name ORDER BY n DESC)       AS rn
    FROM per_nbhd
)
SELECT neighbourhood_name, ward, total AS service_requests, service_category AS top_category,
       round(100.0 * n / total, 1) AS top_category_share_pct
FROM ranked
WHERE rn = 1
ORDER BY total DESC
LIMIT 20;
