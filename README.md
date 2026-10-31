# Retail Analytics Decision Support Platform - Module 3 data pipeline

Reproducible pipeline that prepares the **Online Retail II** transaction data for analytics while addressing governance, privacy and bias.
Continues the Module 1 vision (Ethical AI Charter) and the Module 2 architecture/Privacy Plan.

```
Source CSV -> ingest -> validate bronze -> clean (+pseudonymise) -> transform -> integrate -> validate outputs -> publish
                 \-> profile                                          \-> bias detection   \-> privacy scan
```

Student: Bezzel Chitsungo - MSc Data Analytics, Nexford University - BAN 6800 (Module 3 capstone)
Full architecture, governance and lineage: see `docs/`.

## What is verified and what is not

| Item | Status |
|---|---|
| Pipeline executed end-to-end on the real file (1,067,371 rows) with Prefect | **Executed** - see `reports/latest/run_summary.json` |
| Great Expectations suites (16 bronze + 99 output expectations) and 13 reconciliation checks | **Executed**, all passed on the real data |
| Controlled failing fixture proves a critical failure blocks publication | **Executed** - `reports/evidence/gate_failure_demo.json` |
| Two identical runs produce identical table content hashes | **Executed** - `reports/evidence/reproducibility_check.json` |
| Unit + integration tests | **Executed** - `reports/evidence/pytest_results.txt` |
| Pinned dependencies install cleanly in a fresh virtualenv and tests pass there | **Executed** - `reports/evidence/fresh_venv_check.txt` |
| Docker image build, and the test suite run inside the image | **Executed in CI** - GitHub Actions run #4, commit `dfb67ea`, job `docker` green (see `reports/evidence/ci_run_4.md`). **Not done:** a full-dataset pipeline run inside the container |
| GitHub push / CI workflow | **Executed** - pushed to the repository; `.github/workflows/ci.yml` run #4 passed both jobs (`test`, `docker`): https://github.com/DrChitsungo/https-github.com-users-online-retail-analytics-/actions/runs/40368853759 |
| Scheduling, Key Vault, RBAC, retention automation | **Proposed** only (see `docs/governance.md`) |

## Repository layout

```
configs/pipeline.yaml        every rule, threshold and proposed policy (hashed into each run)
src/retail_pipeline/         ingest, profiling, cleaning, transform, integrate, validation, bias, privacy, audit, publish, flow
gx/expectations/             exported Great Expectations suites (generated from code; scripts/export_gx_suites.py)
docs/                        data_dictionary.yaml|md, lineage.md, governance.md, ethics_privacy_controls.md, architecture.md
reports/latest/              evidence from the latest successful run (profile, validation, reconciliation, bias, privacy, audit)
reports/evidence/            failing-fixture demo, reproducibility check, test output
scripts/                     build_docs, export_gx_suites, demo_gate_failure, verify_reproducibility, build_deck
tests/                       unit + Prefect integration tests (hand-written fixtures, not dataset data)
data/                        (git-ignored) raw/, bronze/, runs/, published/
```

## 1. Setup (local)

Python 3.13 is what was verified.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -c requirements.lock.txt -r requirements.txt     # add: pytest==9.1.1 for tests
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"      # paste the output as CUSTOMER_KEY_SECRET in .env
set -a && source .env && set +a
export PYTHONPATH=src
```

## 2. Data acquisition

The raw data are **not** in Git. Obtain Online Retail II (UCI Machine Learning Repository dataset 502, also mirrored on Kaggle; Chen, 2019) as a single CSV and place it at:

```
data/raw/online_retail_II.csv          # 94,850,204 bytes
sha256: 32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9
```

The supplied archive `online_retail_II.csv.zip` had SHA-256 `cd8933885509825c8e78db04d697c58e62909ded854c4084e094bd31f7e417cc`. The pipeline refuses to run if the CSV checksum differs from `source.expected_sha256` in `configs/pipeline.yaml` (update the pin deliberately if you intentionally use a different version). Download URLs could not be tested from the build environment.

```bash
unzip online_retail_II.csv.zip -d data/raw && sha256sum data/raw/online_retail_II.csv
```

## 3. Run

```bash
python -m retail_pipeline.flow --run-id run-001              # ~40 s on the verified file
python -m retail_pipeline.profiling data/raw/online_retail_II.csv reports/source_profile.json   # standalone profiling
```

Outputs: `data/published/<run_id>/*.parquet` + `MANIFEST.json`, `data/published/LATEST.json`, and evidence in `reports/runs/<run_id>/` (copied to `reports/latest/`).
If any critical gate fails, the flow exits with an error, writes `reports/runs/<run_id>/run_status.json` (`FAILED`, failed tasks) and **publishes nothing**.

## 4. Validate, test, verify

```bash
python -m pytest                                                        # 64 tests: rules, privacy, audit, bias, gates, Prefect flow
python scripts/demo_gate_failure.py run-001 reports/evidence/gate_failure_demo.json      # injected faults must block publication
python -m retail_pipeline.flow --run-id run-002                         # same inputs, config, code, key ...
python scripts/verify_reproducibility.py run-001 run-002 reports/evidence/reproducibility_check.json   # ... identical content hashes
python scripts/build_docs.py                                            # regenerate data_dictionary.md and lineage.md
python scripts/export_gx_suites.py                                      # regenerate gx/expectations/*.json
```

## 5. Docker (image build and in-image tests verified in CI; full-data run in a container not yet done)

```bash
docker build -t retail-pipeline .
docker run --rm --env-file .env --user "$(id -u):$(id -g)" -e PREFECT_HOME=/tmp/.prefect \
  -v "$PWD/data:/app/data" -v "$PWD/reports:/app/reports" retail-pipeline --run-id docker-001
# tests inside the image (they use their own throw-away test secret):
docker run --rm --entrypoint python -e PREFECT_HOME=/tmp/.prefect retail-pipeline -m pytest
```

The secret is passed at run time (`--env-file`), never baked into the image. Dependencies are installed with `-c requirements.lock.txt`.

## 6. Pipeline outputs

| Table | Grain | Primary key |
|---|---|---|
| fact_sales_line | one retained invoice line | line_id |
| dim_product | merchandise stock code | stock_code |
| dim_customer | pseudonymised customer | customer_key |
| dim_date | calendar day | date |
| agg_daily_sales | day x country | invoice_date, country |
| agg_weekly_sku_demand | ISO week x stock code (sparse) | week_start, stock_code |
| agg_customer_rfm_base | pseudonymised customer | customer_key |

Every raw row is accounted for: **raw = retained + quarantined + excluded** (critical reconciliation). Reason codes are in `cleaning.REASON_ORDER` and `reports/latest/cleaning_summary.json`.

## 7. Key design decisions (all evidence-based, see `reports/latest/`)

* **Source blocks / overlap.** The CSV has one backward step in `InvoiceDate` (row 525,461). Records in the overlap window (1-9 Dec 2010) were compared across both blocks; they are identical as multisets, so the block-2 copies are excluded as *confirmed duplicate ingestion*. This is only done if the comparison verifies; otherwise nothing is removed.
* **Within-source exact duplicates** are *retained and flagged* (they may be legitimate repeated scans); `rules.drop_within_source_exact_duplicates` switches this.
* **Cancellations / returns** (negative quantity on `C` invoices) are valid and retained. Negative quantity on a non-cancellation invoice is a stock adjustment and is quarantined.
* **Missing Customer ID** is not an error: those sales stay in revenue/product analytics and are flagged `customer_identified = false`.
* **Pseudonymisation** is a keyed HMAC; the result is pseudonymous, not anonymous.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `SecretError: environment variable CUSTOMER_KEY_SECRET is not set` | Create `.env` from `.env.example`, `set -a; source .env; set +a` |
| `IngestionError: source checksum does not match` | Wrong/modified CSV. Re-download, or deliberately update `source.expected_sha256` |
| `IngestionError: source file not found` | Put the CSV at `data/raw/online_retail_II.csv` |
| `ValidationBlocked: ... critical expectation(s) failed` | See `reports/runs/<run_id>/validation_*.json` (failed expectation names and counts, no record samples) |
| `PublicationBlocked` | A gate failed (validation, bronze, or PII scan); nothing was published; `LATEST.json` is unchanged |
| Prefect prints "temporary server" lines | Normal: Prefect starts a local ephemeral API for the run; state is kept in `.prefect/` (git-ignored) |
| Permission errors writing from Docker | Run with `--user "$(id -u):$(id -g)"` and `-e PREFECT_HOME=/tmp/.prefect` |

## 9. Limitations

* One static source; no ERP/CRM/cost data, so margin and stock-availability KPIs cannot be measured (Module 1/2 constraint).
* Bias findings are internal representation imbalances (no external benchmark, no demographic fields).
* Cancellations cannot be linked to their original sales (cancellation invoice numbers do not match any sale number).
* Overlap evidence is derived from record comparison; the CSV does not record worksheet names, so `source_block` is inferred.
* Retention, access roles, lawful basis, DPIA and incident handling are proposals/organisational tasks (see `docs/governance.md`).


---

## Module 4: 90-day churn model (predictive modelling)

Predicts which identified customers are likely to place **no sales invoice in the next 90 days** (window PROPOSED, pending Marketing). Decision support only; see `docs/MODEL_CARD.md`.

### Verified status (Module 4)

| Item | Status |
|---|---|
| Snapshot dataset, leakage controls, time-ordered splits | **Executed**, covered by `tests/test_churn_model.py` |
| MLflow tracking (experiment `retail-churn-90d`, 32 real runs incl. superseded iteration 1 and one failed run) | **Executed**; export in `reports/mlflow_evidence/`; UI screenshots there |
| MLflow Model Registry (`retail-churn-logreg`, version 1, alias `champion`) | **Executed**; `reports/mlflow_evidence/model_registry.json` and `mlflow_ui_model_registry.png`; the alias is not production approval |
| Baselines + 3 tuned candidates, selection rule, one-time test evaluation | **Executed**; `reports/model/*.json` |
| SHAP / counterfactuals / sensitivity notebook | **Executed** end to end with assertions: `notebooks/shap_analysis.ipynb` |
| Fairness analysis (UK vs non-UK, supplementary) | **Executed**; protected-attribute requirement **unmet** (no such data) |
| FastAPI `/predict` | **Executed** via TestClient and a live server smoke test (see below) |
| Pinned `requirements-ml.txt` installs in a fresh virtualenv and the 27 churn tests pass there (29 now, after the registry tests were added; the fresh-venv log predates them) | **Executed** - `reports/evidence/fresh_venv_check_module4.txt` |
| Cross-artefact consistency (model metadata, MLflow, API, reports) | **Executed** - `scripts/verify_module4.py`, `reports/evidence/module4_verification.txt` |
| AI Disclosure Form | **Drafted**, awaiting the learner's review and sign-off (delivered separately, not in the repo) |
| Push to GitHub of the Module 4 files | **Not done by the assistant**; the user must upload (see delivery notes) |

### Setup

```bash
python -m venv .venv-ml && source .venv-ml/bin/activate
pip install -r requirements-ml.txt
export PYTHONPATH=src MLFLOW_DISABLE_AGENT_HINT=1
```

### Reproduce (needs the Module 3 published fact table at `data/published/run-002/`)

```bash
python -m churn_model.train          # baselines + candidates, validation only; builds data/modeling/churn_snapshots.parquet
python -m churn_model.ablation
python -m churn_model.select         # applies the pre-declared rule + validation fairness gate
python -m churn_model.final_eval     # SCORES THE TEST SET (do this once; re-running is a further look and must be disclosed)
python -m churn_model.mitigation     # exploratory; also touches test
python -m churn_model.explain
python -m churn_model.package_model  # writes models/churn_logreg_v1.0.0.*
python -m churn_model.register_model # registers it in the MLflow Model Registry (version 1, alias champion); idempotent
python -m pytest -q tests/test_churn_model.py
```

Note: the exact numbers in the reports come from the recorded runs; retraining from scratch re-creates runs with new ids.

### MLflow UI

```bash
mlflow ui --backend-store-uri sqlite:///mlruns_store/mlflow.db --default-artifact-root mlruns_store/artifacts --port 5000
```

### Serve the model

```bash
PYTHONPATH=src uvicorn churn_model.api:app --port 8000
# optional: CHURN_MODEL_PATH=/path/to/churn_logreg_v1.0.0.joblib
```

Sample request (`is_single_invoice` is derived by the service; gap fields may be null for single-invoice customers):

```bash
curl -s localhost:8000/predict -H 'content-type: application/json' -d '{
 "recency_days":40,"tenure_days":400,"n_inv_all":6,"n_inv_30":0,"n_inv_90":1,"n_inv_prev90":2,
 "rev_all":1800.5,"rev_90":300,"rev_180":900,"n_products_all":60,"n_products_180":35,
 "avg_units_per_inv":120,"mean_gap_days":55,"std_gap_days":20,"recency_over_gap":0.73,
 "n_cancel_all":0,"cancel_ratio":0}'
```

Verified response shape (values from the recorded smoke test): `{"request_id": "...", "model_version": "1.0.0", "churn_probability": 0.317697, "flagged_high_churn_risk": true, "decision_threshold": 0.313903, "imputed_fields": [], "notes": [...]}`.
Invalid input (for example `n_inv_30` larger than `n_inv_90`) returns HTTP 422 naming the field and rule **without echoing the submitted value**. Request bodies are never logged.

### Module 4 layout

```
configs/churn.yaml                 task, splits, seeds, thresholds (hashed into MLflow runs)
src/churn_model/                   dataset, train, select, final_eval, fairness, mitigation, explain, package_model, register_model, api
notebooks/shap_analysis.ipynb      global/local SHAP, counterfactuals, sensitivity (executed)
reports/Model_Validation_Report.*  validation report; reports/Fairness_Metrics_Report.md
reports/model/                     result JSON + figures; reports/mlflow_evidence/ run export + UI screenshots
docs/MODEL_CARD.md, docs/model_feature_spec.md, docs/requirements_evidence_checklist.md, docs/instructor_clarification_request_DRAFT.md (NOT SENT)
models/churn_logreg_v1.0.0.*       the packaged model and its metadata
```
