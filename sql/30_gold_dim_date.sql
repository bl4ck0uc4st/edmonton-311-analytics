-- Gold: calendar dimension covering the data range plus one full year of headroom.
-- Marked as the date table in Power BI; all time intelligence hangs off this table.
CREATE OR REPLACE TABLE gold.dim_date AS
WITH bounds AS (
    SELECT
        date_trunc('year', min(created_at))::DATE                                   AS start_date,
        (date_trunc('year', max(created_at)) + INTERVAL '2 years' - INTERVAL '1 day')::DATE AS end_date
    FROM silver.requests
),
days AS (
    SELECT unnest(generate_series(start_date::TIMESTAMP, end_date::TIMESTAMP, INTERVAL '1 day'))::DATE AS d
    FROM bounds
)
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER)                        AS date_key,
    d                                                             AS date,
    year(d)                                                       AS year,
    quarter(d)                                                    AS quarter,
    'Q' || quarter(d)                                             AS quarter_name,
    year(d) || ' Q' || quarter(d)                                 AS year_quarter,
    month(d)                                                      AS month,
    strftime(d, '%B')                                             AS month_name,
    strftime(d, '%b')                                             AS month_short,
    year(d) * 100 + month(d)                                      AS year_month_key,
    strftime(d, '%Y-%m')                                          AS year_month,
    strftime(d, '%b %Y')                                          AS month_year_label,
    day(d)                                                        AS day,
    isodow(d)                                                     AS day_of_week,
    strftime(d, '%A')                                             AS day_name,
    strftime(d, '%a')                                             AS day_short,
    isodow(d) IN (6, 7)                                           AS is_weekend,
    weekofyear(d)                                                 AS iso_week,
    CASE WHEN month(d) IN (12, 1, 2) THEN 'Winter'
         WHEN month(d) IN (3, 4, 5)  THEN 'Spring'
         WHEN month(d) IN (6, 7, 8)  THEN 'Summer'
         ELSE 'Fall' END                                          AS season,
    CASE WHEN month(d) IN (12, 1, 2) THEN 1
         WHEN month(d) IN (3, 4, 5)  THEN 2
         WHEN month(d) IN (6, 7, 8)  THEN 3
         ELSE 4 END                                               AS season_sort,
    h.holiday_name IS NOT NULL                                    AS is_holiday,
    h.holiday_name                                                AS holiday_name,
    CASE WHEN h.holiday_name IS NOT NULL THEN 'Holiday'
         WHEN isodow(d) IN (6, 7)   THEN 'Weekend'
         ELSE 'Business day' END                                  AS day_type
FROM days
LEFT JOIN seed.holidays h ON h.holiday_date = d
ORDER BY d;
