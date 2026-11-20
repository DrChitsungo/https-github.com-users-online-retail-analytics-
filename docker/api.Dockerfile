# Model API (Module 4): FastAPI /predict serving the packaged champion model. Used by docker-compose.yml (service "api").
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src \
    CHURN_MODEL_PATH=/app/models/churn_logreg_v1.0.0.joblib
WORKDIR /app
COPY docker/requirements-api.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src/churn_model/__init__.py src/churn_model/api.py ./src/churn_model/
COPY models/churn_logreg_v1.0.0.joblib models/churn_logreg_v1.0.0.metadata.json ./models/
RUN useradd --create-home --uid 10001 api && chown -R api /app
USER api
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2); sys.exit(0)"
CMD ["uvicorn", "churn_model.api:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"]
