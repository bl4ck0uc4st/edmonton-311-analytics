-- Gold: periodic snapshot fact, grain = one row per calendar day x service.
-- Answers "how many service requests were open at the end of day D?" without an
-- expensive event-in-progress calculation at query time. Only requests that were
-- referred to a business area count as backlog; information calls close within minutes.
-- A request is open at end of day D when created_date <= D and (closed_date is null or closed_date > D).
CREATE OR REPLACE TABLE gold.fact_backlog_snapshot AS
WITH spans AS (
    SELECT
        service_key,
        neighbourhood_key,
        created_at::DATE                                                      AS open_from,
        CASE
            -- closed: open through the day before closure (a request closed on its creation
            -- day never appears in an end-of-day backlog). A closed request whose close
            -- timestamp was rejected in silver is treated as closed on its creation day.
            WHEN is_closed THEN least(coalesce(closed_at::DATE, created_at::DATE) - INTERVAL '1 day', DATE '{as_of_date}')::DATE
            ELSE DATE '{as_of_date}'
        END                                                                   AS open_until
    FROM gold.fact_service_request
    WHERE is_service_request
      AND created_at::DATE <= DATE '{as_of_date}'
),
expanded AS (
    SELECT
        service_key,
        unnest(generate_series(open_from::TIMESTAMP, open_until::TIMESTAMP, INTERVAL '1 day'))::DATE AS snapshot_date,
        open_from
    FROM spans
    WHERE open_until >= open_from
)
SELECT
    CAST(strftime(snapshot_date, '%Y%m%d') AS INTEGER)                        AS date_key,
    service_key,
    count(*)                                                                  AS open_requests,
    count(*) FILTER (WHERE date_diff('day', open_from, snapshot_date) > 30)   AS open_over_30_days,
    count(*) FILTER (WHERE date_diff('day', open_from, snapshot_date) > 90)   AS open_over_90_days
FROM expanded
GROUP BY 1, 2
ORDER BY 1, 2;
