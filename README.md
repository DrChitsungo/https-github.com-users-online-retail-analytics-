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
| Docker image build/run | **NOT verified** - Dockerfile provided; no Docker daemon was available where this was built |
| GitHub push / CI workflow | **Pending** - `.github/workflows/ci.yml` (tests + Docker build and in-image tests) counts as evidence only once a green run appears in the repository Actions tab |
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

## 5. Docker (provided, not verified here)

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
