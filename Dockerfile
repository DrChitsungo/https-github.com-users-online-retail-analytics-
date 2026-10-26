# Reproducible runtime for the Retail Analytics pipeline.  Build:  docker build -t retail-pipeline .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    RETAIL_PIPELINE_HOME=/app PYTHONPATH=/app/src \
    PREFECT_HOME=/app/.prefect PREFECT_SERVER_ANALYTICS_ENABLED=false

WORKDIR /app
COPY requirements.txt requirements.lock.txt ./
RUN pip install --no-cache-dir -c requirements.lock.txt -r requirements.txt pytest==9.1.1

COPY src ./src
COPY configs ./configs
COPY docs ./docs
COPY scripts ./scripts
COPY tests ./tests
COPY pytest.ini ./
# files read by tests/test_repo_hygiene.py
COPY .gitignore .env.example Dockerfile README.md ./

# Run as an unprivileged user; data and reports are mounted at runtime, the secret is passed with --env-file/-e.
RUN useradd --create-home --uid 10001 pipeline && mkdir -p /app/data /app/reports /app/.prefect && chown -R pipeline /app
USER pipeline

VOLUME ["/app/data", "/app/reports"]
ENTRYPOINT ["python", "-m", "retail_pipeline.flow"]
CMD []
