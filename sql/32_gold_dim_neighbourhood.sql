-- Gold: neighbourhood dimension with ward roll-up and centroids for map visuals.
-- The source anonymises locations to the neighbourhood centroid, so this is the finest
-- geography available. Requests without a neighbourhood (mostly phone information
-- calls) map to the explicit "Unknown" member (key -1) so no fact row is ever dropped.
CREATE OR REPLACE TABLE gold.dim_neighbourhood AS
WITH src AS (
    SELECT
        neighbourhood_id,
        neighbourhood_name_raw,
        ward,
        round(avg(nbhd_latitude), 6)  AS nbhd_latitude,
        round(avg(nbhd_longitude), 6) AS nbhd_longitude,
        round(avg(ward_latitude), 6)  AS ward_latitude,
        round(avg(ward_longitude), 6) AS ward_longitude,
        count(*)            AS n
    FROM silver.requests
    WHERE neighbourhood_id IS NOT NULL
    GROUP BY 1, 2, 3
),
ranked AS (
    -- a neighbourhood id must map to exactly one name/ward: keep the most frequent spelling
    SELECT *, row_number() OVER (PARTITION BY neighbourhood_id ORDER BY n DESC, neighbourhood_name_raw) AS rn
    FROM src
),
title_cased AS (
    SELECT
        *,
        array_to_string(
            list_transform(
                string_split(lower(coalesce(neighbourhood_name_raw, 'unknown')), ' '),
                w -> CASE WHEN w LIKE 'mc%' AND length(w) > 2
                          THEN 'Mc' || upper(substr(w, 3, 1)) || substr(w, 4)
                          ELSE upper(substr(w, 1, 1)) || substr(w, 2) END
            ),
            ' '
        ) AS neighbourhood_name
    FROM ranked
    WHERE rn = 1
)
SELECT
    neighbourhood_id                              AS neighbourhood_key,
    neighbourhood_id,
    neighbourhood_name,
    neighbourhood_name_raw                        AS neighbourhood_name_source,
    coalesce(ward, 'Unknown')                     AS ward,
    nbhd_latitude,
    nbhd_longitude,
    ward_latitude,
    ward_longitude,
    FALSE                                         AS is_unknown_member
FROM title_cased
UNION ALL
SELECT -1, NULL, 'Unknown / not provided', NULL, 'Unknown', NULL, NULL, NULL, NULL, TRUE
ORDER BY neighbourhood_key;
