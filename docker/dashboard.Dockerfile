# Stakeholder dashboard (Module 5): Streamlit app; calls the API service over the Compose network. Used by docker-compose.yml (service "dashboard").
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CHURN_API_URL=http://api:8000
WORKDIR /app
COPY dashboard/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY dashboard/app.py ./app.py
COPY dashboard/dash_lib ./dash_lib
COPY dashboard/data ./data
RUN useradd --create-home --uid 10001 dash && chown -R dash /app
USER dash
EXPOSE 8501
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=2); sys.exit(0)"
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.headless", "true", "--browser.gatherUsageStats", "false"]
