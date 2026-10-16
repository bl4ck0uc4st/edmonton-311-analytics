-- Gold: service dimension (area -> category -> description hierarchy) enriched with
--   * service_group   : an analyst-defined roll-up of the ~30 business areas (seeds/service_groups.csv)
--   * sla_target_days : illustrative response-time target with precedence
--                       exact (area, category) > (area, any) > global default (seeds/sla_targets.csv)
CREATE OR REPLACE TABLE gold.dim_service AS
WITH distinct_services AS (
    SELECT DISTINCT service_area, service_category, service_description
    FROM silver.requests
),
sla_candidates AS (
    SELECT
        ds.service_area,
        ds.service_category,
        t.target_days,
        t.basis,
        row_number() OVER (
            PARTITION BY ds.service_area, ds.service_category
            ORDER BY (t.service_area IS NOT NULL)::INTEGER + (t.service_category IS NOT NULL)::INTEGER DESC
        ) AS precedence
    FROM (SELECT DISTINCT service_area, service_category FROM distinct_services) ds
    JOIN seed.sla_targets t
      ON (t.service_area IS NULL OR t.service_area = ds.service_area)
     AND (t.service_category IS NULL OR t.service_category = ds.service_category)
)
SELECT
    row_number() OVER (ORDER BY ds.service_area, ds.service_category, ds.service_description) AS service_key,
    ds.service_area,
    ds.service_category,
    ds.service_description,
    coalesce(g.service_group, 'Other')                              AS service_group,
    ds.service_area || ' / ' || ds.service_category                 AS area_category,
    coalesce(sla.target_days, 30)                                   AS sla_target_days,
    coalesce(sla.basis, 'Global default')                           AS sla_basis,
    ds.service_area IN ('311 Call Centre', 'Dropped/Non Service Calls')
        OR ds.service_category IN ('General Information', 'General Inquiry', 'Open 311') AS is_informational
FROM distinct_services ds
LEFT JOIN seed.service_groups g ON g.service_area = ds.service_area
LEFT JOIN sla_candidates sla
       ON sla.service_area = ds.service_area
      AND sla.service_category = ds.service_category
      AND sla.precedence = 1
ORDER BY service_key;
