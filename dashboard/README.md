# Module 5 dashboard (Streamlit)

Stakeholder dashboard for the Module 4 90-day churn model. Five views: Business overview, Results and explanations, Prediction and what-if, Fairness and ethics, About and evidence.

**Why Streamlit on a Hugging Face Docker Space.** The existing code is Python; Streamlit needs no front-end build; and a Docker Space can run the Module 4 FastAPI service beside the dashboard, so live `/predict` calls work from the public URL (Streamlit Community Cloud cannot run a second service).

## Run locally
```bash
pip install -r requirements-ml.txt -r dashboard/requirements.txt
PYTHONPATH=src python scripts/build_dashboard_data.py        # rebuilds dashboard/data/dashboard_evidence.json (needs the git-ignored test predictions)
PYTHONPATH=src uvicorn churn_model.api:app --port 8000 &       # the Module 4 API
CHURN_API_URL=http://127.0.0.1:8000 streamlit run dashboard/app.py
python scripts/api_demo.py --check-parity                      # API demonstration
```
`CHURN_API_URL` is the only setting (see `.env.example`). No secrets are needed.

## Deploy to Hugging Face (manual, needs the owner's account)
1. `python scripts/build_hf_space.py` creates `build/hf_space/` and `build/hf_space.zip`.
2. On huggingface.co create a **Docker (Blank)** Space named `retail-churn-dashboard`, public.
3. Upload the contents of `build/hf_space/` (Dockerfile, README.md, requirements.txt, start.sh, `app/`, `src/`, `models/`, `.streamlit/`) at the Space root and commit. Wait for **Running**.

## Tests
`PYTHONPATH=src python -m pytest tests/test_dashboard.py -q` covers metric maths, parity of the what-if logic with Module 4, API acceptance of every example profile, error handling when the API is unreachable, evidence-file privacy, and a smoke run of every view.

## What is in the public data
Aggregates only (`data/dashboard_evidence.json`): confusion counts per filter, calibration deciles, score histogram, SHAP summaries, fairness tables, and five example profiles rounded for privacy (no identifiers, dates or row indexes).
