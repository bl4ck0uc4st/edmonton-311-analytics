# Data dictionary

Generated from `scripts/powerbi_model_spec.py`. Each table below is exported by `yeg311 export` to
`data/exports/<export>.parquet` (dimensions also as CSV) and loaded into Power BI under the friendly name.

Grain and keys follow Kimball conventions: integer surrogate keys on every dimension, an explicit
`Unknown` member (key `-1`) for missing neighbourhoods, and no fact row is ever dropped because of a
missing dimension value.

## Dim Date  (`dim_date`)

Calendar dimension (one row per day). Marked as the date table; drives all time intelligence.

| Source column | Power BI column | Type | Description |
|---|---|---|---|
| `date_key` | Date Key (hidden) | int64 | Surrogate key yyyymmdd, joins to fact tables |
| `date` | Date | dateTime | Calendar date |
| `year` | Year | int64 | Calendar year |
| `quarter` | Quarter (hidden) | int64 | Quarter number 1-4 |
| `quarter_name` | Quarter Name | string | Q1..Q4 |
| `year_quarter` | Year Quarter | string | e.g. 2026 Q3 |
| `month` | Month (hidden) | int64 | Month number 1-12 |
| `month_name` | Month Name | string | Full month name |
| `month_short` | Month Short | string | Three-letter month |
| `year_month_key` | Year Month Key (hidden) | int64 | yyyymm integer for sorting |
| `year_month` | Year Month | string | yyyy-mm text |
| `month_year_label` | Month Year | string | e.g. Oct 2026 (chart axis label) |
| `day` | Day | int64 | Day of month |
| `day_of_week` | Day Of Week (hidden) | int64 | ISO weekday 1=Monday..7=Sunday |
| `day_name` | Day Name | string | Weekday name |
| `day_short` | Day Short | string | Three-letter weekday |
| `is_weekend` | Is Weekend | boolean | Saturday or Sunday |
| `iso_week` | ISO Week | int64 | ISO week number |
| `season` | Season | string | Winter (Dec-Feb), Spring, Summer, Fall |
| `season_sort` | Season Sort (hidden) | int64 | Season ordering 1-4 |
| `is_holiday` | Is Holiday | boolean | Alberta statutory holiday |
| `holiday_name` | Holiday Name | string | Holiday name when applicable |
| `day_type` | Day Type | string | Business day / Weekend / Holiday |

## Dim Service  (`dim_service`)

Service hierarchy: Service Group > Service Area > Service Category > Service Description, plus illustrative SLA targets.

| Source column | Power BI column | Type | Description |
|---|---|---|---|
| `service_key` | Service Key (hidden) | int64 | Surrogate key |
| `service_area` | Service Area | string | City business area responsible for the request |
| `service_category` | Service Category | string | Type of request (e.g. Potholes, Bylaw Complaints) |
| `service_description` | Service Description | string | Most detailed request description |
| `service_group` | Service Group | string | Analyst roll-up of service areas (seeds/service_groups.csv) |
| `area_category` | Area / Category | string | Area and category concatenated for labels |
| `sla_target_days` | SLA Target Days | int64 | Illustrative response target in days (seeds/sla_targets.csv) |
| `sla_basis` | SLA Basis | string | Where the target came from (exact / area default / global default) |
| `is_informational` | Is Informational | boolean | True for information-only call types |

## Dim Neighbourhood  (`dim_neighbourhood`)

Edmonton neighbourhoods with ward roll-up and centroid coordinates (the finest geography the source publishes).

| Source column | Power BI column | Type | Description |
|---|---|---|---|
| `neighbourhood_key` | Neighbourhood Key (hidden) | int64 | Surrogate key (= neighbourhood id, -1 = Unknown) |
| `neighbourhood_id` | Neighbourhood ID (hidden) | int64 | City of Edmonton neighbourhood number |
| `neighbourhood_name` | Neighbourhood | string | Neighbourhood name (title case) |
| `neighbourhood_name_source` | Neighbourhood (Source) (hidden) | string | Name exactly as published (upper case) |
| `ward` | Ward | string | 2021 City of Edmonton ward (Indigenous names) |
| `nbhd_latitude` | Latitude | double | Neighbourhood centroid latitude |
| `nbhd_longitude` | Longitude | double | Neighbourhood centroid longitude |
| `ward_latitude` | Ward Latitude | double | Ward centroid latitude |
| `ward_longitude` | Ward Longitude | double | Ward centroid longitude |
| `is_unknown_member` | Is Unknown | boolean | True for the Unknown placeholder member |

## Dim Intake  (`dim_intake`)

How a request came in (channel) and whether it became a service request (referral type).

| Source column | Power BI column | Type | Description |
|---|---|---|---|
| `intake_key` | Intake Key (hidden) | int64 | Surrogate key |
| `interaction_channel` | Channel | string | Phone Call, Mobile App, Web Form, ESRI MAP, Email |
| `referral_type` | Referral Type | string | Full Service (answered at first contact) or Referral (sent to a business area) |
| `channel_group` | Channel Group | string | Digital vs Voice |
| `request_type` | Request Type | string | Readable label for referral type |
| `is_service_request` | Is Service Request | boolean | True when the request was referred to a business area |

## Dim Status  (`dim_status`)

Open/Closed plus the outcome detail recorded by the business area.

| Source column | Power BI column | Type | Description |
|---|---|---|---|
| `status_key` | Status Key (hidden) | int64 | Surrogate key |
| `request_status` | Status | string | Open or Closed |
| `status_detail` | Status Detail | string | Outcome / progress note (Not specified when blank) |
| `is_closed_status` | Is Closed | boolean | True when Status = Closed |
| `outcome_group` | Outcome Group | string | Grouping of status details (Resolved, Duplicate, Redirected, ...) |

## Fact Service Request  (`fact_service_request`)

Transaction fact: one row per 311 request with timings, SLA evaluation and foreign keys.

| Source column | Power BI column | Type | Description |
|---|---|---|---|
| `request_id` | Request ID (hidden) | int64 | Source row id |
| `created_at` | Created At (hidden) | dateTime | Request creation timestamp (Edmonton local time) |
| `closed_at` | Closed At (hidden) | dateTime | Close timestamp, blank while open |
| `created_date_key` | Created Date Key (hidden) | int64 | FK to Dim Date (active relationship) |
| `closed_date_key` | Closed Date Key (hidden) | int64 | FK to Dim Date (inactive relationship) |
| `created_hour` | Created Hour | int64 | Hour of day 0-23 the request was created |
| `service_key` | Service Key (hidden) | int64 | FK to Dim Service |
| `neighbourhood_key` | Neighbourhood Key (hidden) | int64 | FK to Dim Neighbourhood |
| `intake_key` | Intake Key (hidden) | int64 | FK to Dim Intake |
| `status_key` | Status Key (hidden) | int64 | FK to Dim Status |
| `is_closed` | Is Closed | boolean | True when the request is closed |
| `is_service_request` | Is Service Request | boolean | Denormalised from Dim Intake for fast filters |
| `resolution_hours` | Resolution Hours | double | Hours from creation to close |
| `resolution_days` | Resolution Days | double | Days from creation to close (fractional) |
| `resolution_calendar_days` | Resolution Calendar Days | int64 | Whole calendar days between create and close dates |
| `sla_target_days` | SLA Target Days (hidden) | int64 | Target applied to this request |
| `sla_met` | SLA Met | boolean | True/False for closed service requests, blank otherwise |
| `open_age_days` | Open Age Days | double | Age of open requests as of the data as-of date |
| `backlog_age_bucket` | Backlog Age Bucket | string | 0-7 / 8-30 / 31-90 / 90+ days (open requests only) |
| `resolution_bucket` | Resolution Bucket | string | Under 1 hour / Same day / 1-7 days / 8-30 / 31-90 / Over 90 |
| `closed_before_created_flag` | Closed Before Created Flag (hidden) | boolean | Source close timestamp preceded creation (rejected) |
| `open_with_close_timestamp_flag` | Open With Close Timestamp Flag (hidden) | boolean | Reported Open but the source carried a close timestamp (rejected) |
| `request_count` | Request Count (hidden) | int64 | Always 1; convenience column |

## Fact Backlog Snapshot  (`fact_backlog_snapshot`)

Periodic snapshot: open service requests at the end of each day, by service.

| Source column | Power BI column | Type | Description |
|---|---|---|---|
| `date_key` | Date Key (hidden) | int64 | FK to Dim Date (snapshot day) |
| `service_key` | Service Key (hidden) | int64 | FK to Dim Service |
| `open_requests` | Open Requests | int64 | Service requests open at end of day |
| `open_over_30_days` | Open Over 30 Days | int64 | Of which older than 30 days |
| `open_over_90_days` | Open Over 90 Days | int64 | Of which older than 90 days |

## Data Quality  (`quality_results`)

Results of the pipeline's data-quality checks for the loaded build.

| Source column | Power BI column | Type | Description |
|---|---|---|---|
| `run_at_utc` | Run At (UTC) | string | When the checks ran |
| `check_name` | Check | string | Check identifier |
| `description` | Description | string | What the check verifies |
| `severity` | Severity | string | critical or warning |
| `value` | Value | double | Measured value (failing rows, %, days) |
| `threshold` | Threshold | double | Maximum acceptable value |
| `unit` | Unit | string | rows / % / days |
| `passed` | Passed | boolean | True when value <= threshold |

## Build Info  (`build_info`)

Key/value metadata about the warehouse build (version, timestamps, row counts).

| Source column | Power BI column | Type | Description |
|---|---|---|---|
| `key` | Key | string | Metadata key |
| `value` | Value | string | Metadata value |

## Relationships

| From | To | Active |
|---|---|---|
| `Fact Service Request[Created Date Key]` | `Dim Date[Date Key]` | yes |
| `Fact Service Request[Closed Date Key]` | `Dim Date[Date Key]` | no (USERELATIONSHIP) |
| `Fact Service Request[Service Key]` | `Dim Service[Service Key]` | yes |
| `Fact Service Request[Neighbourhood Key]` | `Dim Neighbourhood[Neighbourhood Key]` | yes |
| `Fact Service Request[Intake Key]` | `Dim Intake[Intake Key]` | yes |
| `Fact Service Request[Status Key]` | `Dim Status[Status Key]` | yes |
| `Fact Backlog Snapshot[Date Key]` | `Dim Date[Date Key]` | yes |
| `Fact Backlog Snapshot[Service Key]` | `Dim Service[Service Key]` | yes |

## Measures

| Measure | Folder | Format |
|---|---|---|
| Total Requests | 1. Volume | `#,0` |
| Service Requests | 1. Volume | `#,0` |
| First-Contact Resolutions | 1. Volume | `#,0` |
| Service Request Share % | 1. Volume | `0.0%` |
| Closed Requests | 1. Volume | `#,0` |
| Open Requests | 1. Volume | `#,0` |
| Open Service Requests | 1. Volume | `#,0` |
| Closure Rate % | 1. Volume | `0.0%` |
| First Data Date | 1. Volume | `yyyy-mm-dd` |
| Last Data Date | 1. Volume | `yyyy-mm-dd` |
| Days in Period | 1. Volume | `#,0` |
| Requests per Day | 1. Volume | `#,0.0` |
| Service Requests per Day | 1. Volume | `#,0.0` |
| Closed by Close Date | 1. Volume | `#,0` |
| Service Requests Closed by Close Date | 1. Volume | `#,0` |
| Net Backlog Change (Opened - Closed) | 1. Volume | `+#,0;-#,0;0` |
| Median Resolution Days | 2. Resolution | `0.0` |
| Avg Resolution Days | 2. Resolution | `0.0` |
| P90 Resolution Days | 2. Resolution | `0.0` |
| Median Resolution Hours (First Contact) | 2. Resolution | `0.00` |
| Resolved Within 7 Days % | 2. Resolution | `0.0%` |
| SLA Evaluated | 3. SLA | `#,0` |
| SLA Met | 3. SLA | `#,0` |
| SLA Missed | 3. SLA | `#,0` |
| SLA Attainment % | 3. SLA | `0.0%` |
| SLA Attainment Goal % | 3. SLA | `0%` |
| SLA Status | 3. SLA | `-` |
| SLA Target Days (Selected) | 3. SLA | `0` |
| Backlog (Snapshot Sum) | 4. Backlog | `#,0` |
| Backlog (End of Period) | 4. Backlog | `#,0` |
| Backlog Over 30 Days (End of Period) | 4. Backlog | `#,0` |
| Backlog Over 90 Days (End of Period) | 4. Backlog | `#,0` |
| Backlog Aged Over 30 Days % | 4. Backlog | `0.0%` |
| Backlog Change vs Prior Month | 4. Backlog | `+#,0;-#,0;0` |
| Avg Open Age Days | 4. Backlog | `0.0` |
| Requests PY | 5. Time Intelligence | `#,0` |
| Requests YoY % | 5. Time Intelligence | `+0.0%;-0.0%;0.0%` |
| Service Requests PY | 5. Time Intelligence | `#,0` |
| Service Requests YoY % | 5. Time Intelligence | `+0.0%;-0.0%;0.0%` |
| Requests MTD | 5. Time Intelligence | `#,0` |
| Requests YTD | 5. Time Intelligence | `#,0` |
| Requests Rolling 3M Avg | 5. Time Intelligence | `#,0` |
| Requests Last 30 Days | 5. Time Intelligence | `#,0` |
| Requests Prior 30 Days | 5. Time Intelligence | `#,0` |
| Requests 30-Day Change % | 5. Time Intelligence | `+0.0%;-0.0%;0.0%` |
| Mobile App Requests | 6. Channels | `#,0` |
| Mobile App Share % | 6. Channels | `0.0%` |
| Digital Share % | 6. Channels | `0.0%` |
| Phone Share % | 6. Channels | `0.0%` |
| Requests % of Total | 7. Ranking & Share | `0.0%` |
| Service Requests % of Total | 7. Ranking & Share | `0.0%` |
| Category Rank | 7. Ranking & Share | `0` |
| Neighbourhood Rank | 7. Ranking & Share | `0` |
| Top Service Category | 7. Ranking & Share | `-` |
| Top Neighbourhood | 7. Ranking & Share | `-` |
| DQ Checks Total | 8. Data Quality | `0` |
| DQ Checks Passed | 8. Data Quality | `0` |
| DQ Status | 8. Data Quality | `-` |
| Pipeline Built At (UTC) | 8. Data Quality | `-` |
| Pipeline Version | 8. Data Quality | `-` |
| Fact Rows (Build) | 8. Data Quality | `#,0` |
| Selected Period Label | 9. Labels | `-` |
| Data As Of Label | 9. Labels | `-` |
| Overview Title | 9. Labels | `-` |

Full DAX for every measure: [`powerbi/dax/measures.dax`](../powerbi/dax/measures.dax).
