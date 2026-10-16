-- Gold: transaction fact table, grain = one 311 request.
-- Foreign keys resolve to the dimensions built just before this step; {as_of_ts} is the
-- pipeline's "as of" timestamp (latest request in the data) used for open-request ageing
-- so results are reproducible regardless of when the build runs.
CREATE OR REPLACE TABLE gold.fact_service_request AS
SELECT
    r.request_id,
    r.created_at,
    r.closed_at,
    CAST(strftime(r.created_at, '%Y%m%d') AS INTEGER)                       AS created_date_key,
    CAST(strftime(r.closed_at, '%Y%m%d') AS INTEGER)                        AS closed_date_key,
    hour(r.created_at)                                                      AS created_hour,
    s.service_key,
    coalesce(n.neighbourhood_key, -1)                                       AS neighbourhood_key,
    i.intake_key,
    st.status_key,
    st.is_closed_status                                                     AS is_closed,
    i.is_service_request                                                    AS is_service_request,
    date_diff('second', r.created_at, r.closed_at) / 3600.0                 AS resolution_hours,
    date_diff('second', r.created_at, r.closed_at) / 86400.0                AS resolution_days,
    date_diff('day', r.created_at::DATE, r.closed_at::DATE)                 AS resolution_calendar_days,
    s.sla_target_days,
    CASE WHEN NOT i.is_service_request THEN NULL
         WHEN r.closed_at IS NULL THEN NULL
         ELSE date_diff('second', r.created_at, r.closed_at) / 86400.0 <= s.sla_target_days
    END                                                                     AS sla_met,
    CASE WHEN NOT st.is_closed_status
         THEN date_diff('second', r.created_at, TIMESTAMP '{as_of_ts}') / 86400.0
    END                                                                     AS open_age_days,
    CASE
        WHEN st.is_closed_status THEN NULL
        WHEN date_diff('day', r.created_at::DATE, DATE '{as_of_date}') <= 7  THEN '0-7 days'
        WHEN date_diff('day', r.created_at::DATE, DATE '{as_of_date}') <= 30 THEN '8-30 days'
        WHEN date_diff('day', r.created_at::DATE, DATE '{as_of_date}') <= 90 THEN '31-90 days'
        ELSE '90+ days'
    END                                                                     AS backlog_age_bucket,
    CASE
        WHEN r.closed_at IS NULL THEN NULL
        WHEN date_diff('second', r.created_at, r.closed_at) < 3600          THEN 'Under 1 hour'
        WHEN date_diff('second', r.created_at, r.closed_at) < 86400         THEN 'Same day'
        WHEN date_diff('second', r.created_at, r.closed_at) < 7 * 86400     THEN '1-7 days'
        WHEN date_diff('second', r.created_at, r.closed_at) < 30 * 86400    THEN '8-30 days'
        WHEN date_diff('second', r.created_at, r.closed_at) < 90 * 86400    THEN '31-90 days'
        ELSE 'Over 90 days'
    END                                                                     AS resolution_bucket,
    r.closed_before_created_flag,
    r.open_with_close_timestamp_flag,
    1                                                                       AS request_count
FROM silver.requests r
JOIN gold.dim_service s
  ON s.service_area = r.service_area
 AND s.service_category = r.service_category
 AND s.service_description = r.service_description
LEFT JOIN gold.dim_neighbourhood n
  ON n.neighbourhood_id = r.neighbourhood_id
JOIN gold.dim_intake i
  ON i.interaction_channel = r.interaction_channel
 AND i.referral_type = r.referral_type
JOIN gold.dim_status st
  ON st.request_status = r.request_status
 AND st.status_detail = coalesce(r.status_detail, 'Not specified')
ORDER BY r.created_at, r.request_id;
