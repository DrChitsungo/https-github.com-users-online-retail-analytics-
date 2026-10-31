#!/usr/bin/env bash
# Starts the Module 4 API on the container loopback, waits until it is healthy, then starts the dashboard on the public port.
set -euo pipefail
python -m uvicorn churn_model.api:app --host 127.0.0.1 --port 8000 --log-level warning &
for i in $(seq 1 60); do
  if python - <<'PY'
import urllib.request, sys
try: urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2); sys.exit(0)
except Exception: sys.exit(1)
PY
  then echo "model API healthy"; break; fi
  sleep 1
done
exec streamlit run app/app.py --server.port 7860 --server.address 0.0.0.0 --server.headless true --server.enableXsrfProtection false --server.enableCORS false --browser.gatherUsageStats false
