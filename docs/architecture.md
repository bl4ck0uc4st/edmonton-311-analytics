# Architecture notes

## Source

`311 Requests` (dataset `q7ua-agfg`) on the City of Edmonton Open Data Portal (Socrata). Rolling window: the
current calendar year plus the previous two (January of year-2 onward). Roughly 1.2 million rows per year.
Locations are anonymised by the City to the neighbourhood centroid. The portal updates the dataset several
times a day.

Observed values that shaped the design:

| Attribute | Values | Modelling consequence |
|---|---|---|
| `referral_type` | Full Service (about 57%), Referral (about 42%), blank | "Service request" = Referral. Full Service calls close within seconds and would otherwise dominate SLA and resolution metrics |
| `interaction_channel` | Phone Call (about 75%), Mobile App (about 21%), Web Form, ESRI MAP, Email | Channel group Digital vs Voice; mobile adoption is a KPI |
| `request_status` | Open, Closed | About 1% open at any time; backlog needs point-in-time logic |
| `status_detail` | about 20 free-text outcomes, mostly blank | Grouped into outcome groups in `dim_status` |
| category labels | double spaces inside labels ("Snow  and  Ice"), occasional blanks | Whitespace normalisation in silver, explicit `Unclassified` member |
| `neighbourhood` | upper case names, missing for most phone information calls | Title-cased display name, `Unknown` member keyed `-1` |
| `ward` | 2021 Indigenous ward names (e.g. papastew, O-day'min) | Kept exactly as published |

## Layers

### Bronze (`data/raw/311_requests/year=YYYY/month=MM/part-0.parquet`)

* All columns stored as strings exactly as the API returned them; typing is deferred to silver so a bad value
  can never break ingestion.
* Written atomically (temp file + rename) with zstd compression; `_manifest.json` records rows and timestamps
  per partition.
* `hive_partitioning = true` lets DuckDB prune months when needed.

### Silver (`silver.requests`)

* `try_cast` for every typed column; rows without a parseable creation timestamp are dropped (counted in the
  quality report through the bronze vs silver difference).
* De-duplication keeps, per `row_id`, the version with a close timestamp first, then the latest creation
  timestamp, because the portal re-publishes a request when its status changes.
* A close timestamp earlier than creation is set to NULL and flagged (`closed_before_created_flag`); the
  request keeps its reported `Closed` status so backlog counts remain correct.

### Gold (star schema)

* Conformed `dim_date` (one row per day, Alberta statutory holidays from the `holidays` library, season,
  day type) shared by both facts.
* `dim_service` carries the natural hierarchy plus two analyst enrichments from seeds: `service_group` and an
  illustrative `sla_target_days` resolved with precedence (area+category > area > global).
* `dim_intake` is a junk dimension of channel x referral type with derived `request_type` and `is_service_request`.
* `fact_service_request` (transaction grain) stores timings, SLA evaluation and ageing buckets computed against
  the pipeline's as-of timestamp (the latest request in the data) so every build is reproducible.
* `fact_backlog_snapshot` (periodic snapshot grain: day x service) expands each service request over the days it
  was open with `generate_series` and aggregates; a request closed on its creation day never counts, and the
  reconciliation check proves the snapshot equals a direct point-in-time count.
* `agg_daily_requests` is a convenience aggregate whose totals are reconciled to the fact table on every run.

## Incremental strategy

| Run type | Months re-extracted | Why |
|---|---|---|
| incremental (weekly) | last 3 (configurable `YEG311_LOOKBACK_MONTHS`) | catches status changes on recent requests; cheap |
| full (monthly) | every month in the rolling window | catches long-running requests closed outside the window and any source restatement |

Because partitions are keyed by creation month and the warehouse is rebuilt from all partitions, re-extracting a
month simply overwrites its file; there is no merge logic to get wrong.

## Scaling notes

* DuckDB builds the 700k-row synthetic scale test in about 4 seconds on 4 threads; the real 3.5M rows build in
  well under a minute on a GitHub-hosted runner.
* The Power BI model imports `fact_service_request` (3.5M rows) comfortably; the two timestamp columns are the
  largest contributors to model size and can be dropped from the import if needed because all time analysis uses
  the integer date keys.
* To move this to Azure: swap the bronze folder for ADLS/Blob, run the same SQL in Fabric Lakehouse or Synapse
  serverless, and point the Power BI parameters at the lakehouse. The medallion layout maps one-to-one.
