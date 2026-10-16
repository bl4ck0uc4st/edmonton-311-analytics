-- Gold: intake ("junk") dimension combining the two low-cardinality attributes that
-- describe HOW a request entered the system and whether it became real work:
--   interaction_channel : Phone Call, Mobile App, Web Form, ESRI MAP, Email
--   referral_type       : Full Service (answered at first contact) vs Referral (sent to a business area)
CREATE OR REPLACE TABLE gold.dim_intake AS
WITH combos AS (
    SELECT DISTINCT interaction_channel, referral_type
    FROM silver.requests
)
SELECT
    row_number() OVER (ORDER BY interaction_channel, referral_type) AS intake_key,
    interaction_channel,
    referral_type,
    CASE WHEN interaction_channel IN ('Mobile App', 'Web Form', 'ESRI MAP', 'Email') THEN 'Digital'
         WHEN interaction_channel = 'Phone Call' THEN 'Voice'
         ELSE 'Other' END                                               AS channel_group,
    CASE referral_type
         WHEN 'Referral'     THEN 'Service request (referred to business area)'
         WHEN 'Full Service' THEN 'Resolved at first contact'
         ELSE 'Unknown' END                                             AS request_type,
    referral_type = 'Referral'                                          AS is_service_request
FROM combos
ORDER BY intake_key;
