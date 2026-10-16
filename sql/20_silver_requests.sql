-- Silver: typed, cleaned and de-duplicated 311 requests (one row per request).
--
-- Cleaning rules (documented in docs/data_dictionary.md):
--   * trim + collapse repeated whitespace ("Snow  and  Ice" -> "Snow and Ice"), blank -> NULL
--   * safe casts with try_cast so one bad value never fails the whole load
--   * the portal re-publishes a request when its status changes; keep the most complete
--     version (closed beats open, then the latest created_at)
--   * a close timestamp earlier than the create timestamp is impossible: null it out and
--     flag the row so the data-quality report can count it
CREATE OR REPLACE TABLE silver.requests AS
WITH cleaned AS (
    SELECT
        try_cast(row_id AS BIGINT)                                                  AS request_id,
        row_id                                                                      AS request_id_raw,
        try_cast(date_created AS TIMESTAMP)                                         AS created_at,
        try_cast(date_closed AS TIMESTAMP)                                          AS closed_at_raw,
        nullif(regexp_replace(trim(request_status), '\s+', ' ', 'g'), '')           AS request_status,
        nullif(regexp_replace(trim(status_detail), '\s+', ' ', 'g'), '')            AS status_detail,
        nullif(regexp_replace(trim(service_area), '\s+', ' ', 'g'), '')             AS service_area,
        nullif(regexp_replace(trim(service_category), '\s+', ' ', 'g'), '')         AS service_category,
        nullif(regexp_replace(trim(service_description), '\s+', ' ', 'g'), '')      AS service_description,
        nullif(regexp_replace(trim(interaction_channel), '\s+', ' ', 'g'), '')      AS interaction_channel,
        nullif(regexp_replace(trim(referral_type), '\s+', ' ', 'g'), '')            AS referral_type,
        try_cast(neighbourhood_id AS INTEGER)                                       AS neighbourhood_id,
        nullif(regexp_replace(trim(neighbourhood), '\s+', ' ', 'g'), '')            AS neighbourhood_name_raw,
        nullif(regexp_replace(trim(ward), '\s+', ' ', 'g'), '')                     AS ward,
        try_cast(nbhd_latitude AS DOUBLE)                                           AS nbhd_latitude,
        try_cast(nbhd_longitude AS DOUBLE)                                          AS nbhd_longitude,
        try_cast(ward_latitude AS DOUBLE)                                           AS ward_latitude,
        try_cast(ward_longitude AS DOUBLE)                                          AS ward_longitude,
        CAST(year AS INTEGER)                                                       AS partition_year,
        CAST(month AS INTEGER)                                                      AS partition_month
    FROM bronze.requests
    WHERE row_id IS NOT NULL
      AND try_cast(date_created AS TIMESTAMP) IS NOT NULL
),
deduped AS (
    SELECT *
    FROM cleaned
    QUALIFY row_number() OVER (
        PARTITION BY request_id_raw
        ORDER BY closed_at_raw DESC NULLS LAST, created_at DESC
    ) = 1
),
statused AS (
    SELECT
        *,
        coalesce(request_status, CASE WHEN closed_at_raw IS NULL THEN 'Open' ELSE 'Closed' END) AS request_status_final
    FROM deduped
)
SELECT
    request_id,
    request_id_raw,
    created_at,
    CASE
        WHEN request_status_final = 'Open' THEN NULL                      -- an open request has no valid close time
        WHEN closed_at_raw IS NOT NULL AND closed_at_raw < created_at THEN NULL
        ELSE closed_at_raw
    END                                                                                               AS closed_at,
    (closed_at_raw IS NOT NULL AND closed_at_raw < created_at)                                        AS closed_before_created_flag,
    (request_status_final = 'Open' AND closed_at_raw IS NOT NULL)                                     AS open_with_close_timestamp_flag,
    request_status_final                                                                              AS request_status,
    status_detail,
    coalesce(service_area, 'Unclassified')                                                            AS service_area,
    coalesce(service_category, 'Unclassified')                                                        AS service_category,
    coalesce(service_description, 'Unclassified')                                                     AS service_description,
    coalesce(interaction_channel, 'Unknown')                                                          AS interaction_channel,
    coalesce(referral_type, 'Unknown')                                                                AS referral_type,
    neighbourhood_id,
    neighbourhood_name_raw,
    ward,
    nbhd_latitude,
    nbhd_longitude,
    ward_latitude,
    ward_longitude,
    partition_year,
    partition_month
FROM statused;
