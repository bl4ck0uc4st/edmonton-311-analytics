# Publishing checklist

Everything to go from this folder to a public portfolio repo with live data and a finished dashboard.

## 1. Push to GitHub (10 minutes)

```bash
cd edmonton-311-analytics
git init -b main
git add .
git commit -m "Edmonton 311 analytics platform: pipeline, warehouse, quality gate, Power BI model"
# create an empty public repo named edmonton-311-analytics on github.com (no README, no .gitignore), then:
git remote add origin https://github.com/bl4ck0uc4st/edmonton-311-analytics.git
git push -u origin main
```

Repo settings:

* **About**: add the description "End-to-end analytics on Edmonton's live 311 data: Python + DuckDB star schema,
  data-quality gates, GitHub Actions refresh, Power BI model as code" and topics
  `power-bi`, `dax`, `duckdb`, `data-engineering`, `etl`, `open-data`, `edmonton`, `star-schema`, `github-actions`.
* **Actions > General**: Workflow permissions = "Read and write permissions" (the refresh workflow creates a release).
* **Secrets** (optional but recommended): `SOCRATA_APP_TOKEN` from https://data.edmonton.ca/profile/edit/developer_settings.

## 2. First live refresh (15 minutes, runs on GitHub's servers)

* Actions > **Refresh data** > Run workflow > mode `full`.
* When it finishes, the workflow commits refreshed preview charts (`docs/img/charts`) and `docs/latest_stats.md`
  to `main` under your name, so the README shows live numbers. Also check the job summary and the **data-latest** release under Releases:
  `fact_service_request.parquet`, the dimension files, `metadata.json`, `quality_report.json`, `headline_stats.txt`.
* The CI badge and the Refresh badge in the README turn green.

## 3. Build the Power BI report (an afternoon)

* Follow `powerbi/README.md` (Path A: TMDL script; Path B: manual) with `DataSourceMode = GitHub Release`.
* Build the five pages from `powerbi/dashboard_spec.md`. Keep it clean: one question per page.
* Save as `powerbi/Edmonton 311 Analytics.pbix`, export each page as PNG to `docs/img/`
  (`01_overview.png`, `02_operations_sla.png`, `03_neighbourhoods.png`, `04_seasonality.png`, `05_data_quality.png`),
  uncomment the image links in `README.md`, commit and push.
* Optional: publish to Power BI Service and add a public "Publish to web" link to the README if your account allows it.

## 4. Fill in the real numbers

* Run `yeg311 run --mode full` locally once (or read `headline_stats.txt` from the release) and replace the
  bracketed placeholders in `docs/resume_bullets.md`.
* Add two or three real findings to the README (for example the top three request types, the share of mobile-app
  intake, the service area with the lowest SLA attainment).

## 5. Make it visible

* Pin the repo on your GitHub profile; add the link to your resume header and LinkedIn Featured section.
* Post the LinkedIn text from `docs/resume_bullets.md` with two dashboard screenshots.
* Rehearse the walkthrough in `docs/interview_guide.md` out loud once; it should take about five minutes.

## Keeping it fresh

* The scheduled workflow keeps the release current without any action from you.
* Every few months re-open the `.pbix`, refresh, re-export screenshots, and bump the numbers in the README.
