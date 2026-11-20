# Batch monitoring and release gates. Used by docker-compose.yml (services "monitoring" and "release-gates", both on demand).
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src MPLCONFIGDIR=/tmp/mpl
WORKDIR /app
COPY requirements-monitoring.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src/churn_model/__init__.py src/churn_model/monitoring.py src/churn_model/release_gates.py ./src/churn_model/
COPY models/churn_logreg_v1.0.0.joblib models/churn_logreg_v1.0.0.metadata.json ./models/
COPY configs/monitoring.yaml configs/release_gates.yaml configs/churn.yaml ./configs/
RUN useradd --create-home --uid 10001 mon && mkdir -p /app/reports /app/dashboard/data /app/data && chown -R mon /app
USER mon
ENTRYPOINT ["python", "-m"]
CMD ["churn_model.monitoring"]
