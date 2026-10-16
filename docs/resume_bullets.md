# Resume and LinkedIn copy

Dense, tool-first bullets. Replace the bracketed numbers with the output of `yeg311 stats` after the first real run.

## Resume: Projects section

**Edmonton 311 Service Request Analytics Platform** | Python, DuckDB, SQL, Power BI (DAX, Power Query, TMDL), GitHub Actions
github.com/bl4ck0uc4st/edmonton-311-analytics

* Python/Socrata API: built a monthly-partitioned, retrying extraction pipeline that pulls [3.5M] City of Edmonton 311 requests into Parquet, with incremental lookback refreshes and a manifest for auditability.
* DuckDB/SQL: designed a Kimball star schema (transaction fact, daily backlog snapshot fact, 5 conformed dimensions) with versioned bronze/silver/gold transformations that clean, type and de-duplicate source data in under a minute per full rebuild.
* Data quality: implemented 19 automated checks (uniqueness, referential integrity, cross-table reconciliation, freshness) with severity levels that gate publishing and surface on a dedicated report page.
* Power BI: modelled 64 DAX measures (time intelligence, SLA attainment, end-of-period backlog via LASTNONBLANK, inactive-relationship USERELATIONSHIP patterns), row-level security by ward, a custom theme and a 5-page report; model defined as code in M/DAX/TMDL and generated from one spec.
* CI/CD: GitHub Actions run lint, 24 tests and a pipeline smoke on every push, and a scheduled workflow refreshes live data weekly and publishes exports to a GitHub Release that Power BI reads directly.

## Shorter variant (3 bullets)

* Built an end-to-end BI platform on Edmonton's live 311 open data ([3.5M] rows): Python extraction, DuckDB star schema, automated data-quality gate, scheduled GitHub Actions refresh.
* Delivered a 5-page Power BI report with 64 DAX measures, time intelligence, RLS and a code-defined semantic model (M, DAX, TMDL).
* Engineered a periodic backlog snapshot fact and reconciliation checks so backlog and SLA KPIs are fast and verifiable.

## LinkedIn post (first-person)

I built a complete analytics platform on Edmonton's live 311 service-request data, the same kind of reporting
problem the City, EPCOR or any utility deals with every day.

What it does: a Python pipeline pulls ~3.5M requests from the City's open data API, DuckDB turns them into a
star schema, 19 data-quality checks decide whether a build is good enough to publish, GitHub Actions refreshes it
every week, and a Power BI report (64 DAX measures, SLA tracking, backlog ageing, neighbourhood maps, row-level
security) sits on top.

What I learned: incremental loads are harder than they look when records change status after creation; a
precomputed backlog snapshot beats clever DAX; and defining a Power BI model as code (M, DAX, TMDL) makes it
reviewable like any other software.

Repo and dashboard screenshots: github.com/bl4ck0uc4st/edmonton-311-analytics

## Skills keywords covered (for ATS)

Power BI, DAX, Power Query (M), TMDL, data modelling, star schema, Kimball, SQL, DuckDB, Parquet, Python,
pandas, pyarrow, ETL/ELT, REST API (Socrata/SODA), incremental loads, data quality, pytest, GitHub Actions,
CI/CD, row-level security, time intelligence, KPI design, SLA reporting, open data, municipal analytics.
