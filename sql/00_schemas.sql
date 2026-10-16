-- Medallion-style layering inside a single DuckDB file.
--   bronze : raw API payload, untyped, partitioned by month (views over Parquet)
--   silver : typed, de-duplicated, cleaned request records
--   gold   : Kimball star schema consumed by Power BI
--   seed   : small reference tables maintained in /seeds (CSV, version controlled)
--   meta   : build metadata and data-quality results
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS seed;
CREATE SCHEMA IF NOT EXISTS meta;
