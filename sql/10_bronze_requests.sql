-- Bronze: a view over the hive-partitioned Parquet landing zone written by the extractor.
-- Every column is VARCHAR on purpose; this layer is an auditable copy of the API payload.
-- {raw_glob} is injected by the pipeline (data/raw/311_requests/year=*/month=*/*.parquet).
CREATE OR REPLACE VIEW bronze.requests AS
SELECT *
FROM read_parquet('{raw_glob}', hive_partitioning = true, union_by_name = true);
