.PHONY: setup lint test sample pipeline refresh assets clean

PY ?= python

setup:            ## install the package with dev tools
	$(PY) -m pip install -e ".[dev]"

lint:             ## ruff lint + format check
	ruff check src tests scripts && ruff format --check src tests scripts

test:             ## run the test suite
	pytest -q

sample:           ## offline demo: synthetic data -> warehouse -> quality -> exports
	yeg311 run --sample --rows 50000

pipeline:         ## real data, incremental refresh (set SOCRATA_APP_TOKEN for higher rate limits)
	yeg311 run --mode incremental

refresh:          ## real data, full refresh of the rolling 3-year window
	yeg311 run --mode full

assets:           ## regenerate Power BI M / DAX / TMDL and the data dictionary from the model spec
	$(PY) scripts/build_powerbi_assets.py

clean:            ## remove generated data (keeps the committed sample)
	rm -rf data/raw/year=* data/raw/311_requests data/warehouse/*.duckdb data/warehouse/*.json data/exports/*.parquet data/exports/*.csv data/exports/*.json data/exports/*.txt

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'
