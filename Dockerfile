# Minimal image to run the pipeline anywhere (CI runners, a cron box, a laptop without Python).
#   docker build -t yeg311 .
#   docker run --rm -v "$PWD/data:/app/data" -e SOCRATA_APP_TOKEN yeg311 run --mode incremental
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY sql ./sql
COPY seeds ./seeds
RUN pip install --no-cache-dir .

ENV YEG311_PROJECT_ROOT=/app
VOLUME ["/app/data"]
ENTRYPOINT ["yeg311"]
CMD ["--help"]
