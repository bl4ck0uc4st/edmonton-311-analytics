-- Gold: status dimension (Open/Closed plus the free-text outcome detail the business area recorded).
CREATE OR REPLACE TABLE gold.dim_status AS
WITH combos AS (
    SELECT DISTINCT
        request_status,
        coalesce(status_detail, 'Not specified') AS status_detail
    FROM silver.requests
)
SELECT
    row_number() OVER (ORDER BY request_status, status_detail) AS status_key,
    request_status,
    status_detail,
    request_status = 'Closed'                                  AS is_closed_status,
    CASE
        WHEN status_detail ILIKE '%duplicate%'                                 THEN 'Duplicate'
        WHEN status_detail ILIKE '%complied%' OR status_detail ILIKE '%remedied%'
          OR status_detail ILIKE '%enforcement action%'                        THEN 'Resolved / Complied'
        WHEN status_detail ILIKE '%deferred%' OR status_detail ILIKE '%work planned%'
          OR status_detail ILIKE '%assessment in progress%'
          OR status_detail ILIKE '%investigation%'                             THEN 'In progress / Planned'
        WHEN status_detail ILIKE '%non-city%' OR status_detail ILIKE '%redirect%'
          OR status_detail ILIKE '%external%'                                  THEN 'Redirected / Out of scope'
        WHEN status_detail ILIKE '%information required%'
          OR status_detail ILIKE '%insufficient%'
          OR status_detail ILIKE '%location not found%'                        THEN 'Needs more information'
        WHEN status_detail ILIKE '%does not meet%' OR status_detail ILIKE '%no action%' THEN 'No action required'
        WHEN status_detail ILIKE '%citizen%'                                   THEN 'Citizen contact'
        WHEN status_detail = 'Not specified'                                   THEN 'Not specified'
        ELSE 'Other' END                                       AS outcome_group
FROM combos
ORDER BY status_key;
