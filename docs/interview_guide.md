# Interview guide: talking about this project

Use this to prepare. It covers the 60-second pitch, the walkthrough, the questions interviewers ask about
projects like this, and honest answers about limits. Everything here is backed by code in the repo, so you can
open the file while you talk.

## 60-second pitch

"I built an end-to-end analytics platform on Edmonton's live 311 dataset, about 3.5 million service requests.
A Python pipeline pulls the data from the City's Socrata API month by month, lands it as Parquet, and DuckDB
transforms it into a star schema: a request fact, a daily backlog snapshot fact and five dimensions. Nineteen
data-quality checks run after every build and block publishing if anything critical fails. GitHub Actions
refreshes it weekly and publishes the exports to a release that Power BI reads directly. The Power BI side has
64 DAX measures, time intelligence, an inactive relationship for closed-by-date analysis, row-level security by
ward, and five report pages. The whole semantic model is defined as code so the M, DAX and documentation never drift."

## Walkthrough order (5 minutes)

1. `README.md` architecture diagram: source -> bronze -> silver -> gold -> quality gate -> release -> Power BI.
2. `src/yeg311/extract.py`: month windows, pagination, retries, atomic partition writes, manifest.
3. `sql/20_silver_requests.sql`: cleaning rules and status-aware de-duplication (`QUALIFY row_number()`).
4. `sql/40_gold_fact_service_request.sql` and `sql/41_gold_fact_backlog_snapshot.sql`: two grains, why both.
5. `src/yeg311/quality.py`: severity model, reconciliation checks, how CI uses the exit code.
6. `.github/workflows/refresh-data.yml`: cache of raw partitions, mode selection, release publishing.
7. `powerbi/dax/measures.dax`: pick three measures (SLA Attainment %, Backlog (End of Period), Requests YoY %).
8. The dashboard itself.

## Likely questions and strong answers

**Why DuckDB and not SQL Server / Postgres?**
It is an analytical (columnar) engine that runs in-process, reads Parquet natively and needs no server, which
makes the pipeline runnable on a laptop and in CI identically. The SQL is standard enough that the same files
would run on Synapse serverless, Fabric or BigQuery with minimal changes. For an enterprise deployment the
warehouse would move to the organisation's platform; the layering and tests would not change.

**Why a star schema instead of one wide table?**
Power BI's engine (VertiPaq) is optimised for star schemas: small dimensions, one filter direction, integer keys.
It keeps measures simple, makes slicers cheap, avoids many-to-many ambiguity, and lets the two facts (transaction
and snapshot) share conformed dimensions such as date and service.

**How does the incremental load work, and what is the trap?**
Requests change status after creation, so "new rows since last run" would freeze each request at its first
status. I partition by creation month and re-extract a lookback window of recent months, with a monthly full
refresh to catch long-lived requests. Re-extracting a month overwrites its partition, so there is no merge logic.

**How do you know the data is right?**
Automated checks on every build: uniqueness at the fact grain, referential integrity for every foreign key,
no negative resolution times, reconciliation between the fact table, the backlog snapshot and the daily
aggregate, plus anomaly-rate and freshness warnings. Critical failures return exit code 1 so the workflow stops
before the release is updated. The same results are visible on the report's Data Quality page.

**Explain the backlog measure.**
"Open at end of day D" means created on or before D and not closed by D. Computing that live in DAX over 3.5M
rows for every point on a chart is slow, so the pipeline precomputes a periodic snapshot (day x service). In
Power BI, `Backlog (End of Period)` uses `LASTNONBLANK` to pick the last day with a snapshot inside whatever
period the user selected, so the same measure works on a card, a monthly line or a quarterly bar.

**Why is there an inactive relationship?**
The fact has two dates: created and closed. The active relationship is on creation date (what most questions
ask). `Closed by Close Date` activates the second relationship with `USERELATIONSHIP` so you can compare requests
opened versus closed in the same period and derive the net backlog change.

**What are the SLA targets?**
Illustrative targets kept in a seed CSV with a precedence rule (area+category, then area, then a global default).
The City does not publish per-category standards in this dataset, so the report labels them as illustrative and
shows the basis in tooltips. Replacing them with official standards is a CSV edit and a rebuild.

**What was the messiest part of the data?**
Labels with repeated internal spaces, blank categories, missing neighbourhoods for phone calls, duplicate
publications of the same request at different statuses, and a handful of close timestamps earlier than the
creation timestamp. Each has an explicit rule in silver and a check that counts how often it happens.

**How would you productionise this on Azure / Fabric?**
Land bronze in ADLS, run the same SQL in a Fabric Lakehouse or Synapse serverless (or Databricks SQL), schedule
with Fabric pipelines or ADF, publish the semantic model with deployment pipelines, and keep the quality checks as
a gate before deployment. The pipeline is already parameterised by environment variables and container-ready.

**Performance considerations in Power BI?**
Integer surrogate keys, no bi-directional relationships, measures instead of calculated columns, hidden
high-cardinality columns, a dedicated measures table, and a precomputed snapshot for the heaviest question.
Time intelligence relies on a proper marked date table.

**Row-level security?**
Two roles: a static ward filter (for demos) and a dynamic one that looks up `USERPRINCIPALNAME()` in a
user-to-ward mapping table, so one report can serve many ward offices.

## Limits to acknowledge (and how you would address them)

* The dataset is anonymised to neighbourhood centroids; point-level maps would need the separate 311 Explorer dataset.
* No population data yet, so volumes are not normalised per resident (roadmap item).
* SLA targets are illustrative.
* The synthetic sample is for tests and demos only; all published numbers come from the live dataset.

## Resume-ready metrics (confirm from `yeg311 stats` after the first real run)

* Rows processed per full refresh, build time, number of quality checks, number of DAX measures, refresh cadence.
