# Pipeline architecture and connection to Module 2

```
 Online Retail II CSV            (single source; static historical snapshot)
        |
        v
 [1 ingest]  verify pinned SHA-256 -> read all fields as text -> bronze parquet (read-only, content-addressed) + manifest
        |------------------------------> [2 profile_source]   measured quality profile (parallel branch)
        v
 [3 validate_bronze]  GX critical gate on schema, required fields, parseability, row count >= 5,000
        v
 [4 clean]            parse -> verified overlap detection -> rule dispositions with reason codes -> keyed pseudonymisation
        |                     retained / quarantined (QRN_*) / excluded (EXC_*)  - every raw row accounted for
        v
 [5 transform]        line_revenue, is_cancellation, deterministic line_id, duplicate flag
        v
 [6 integrate]        fact_sales_line + dim_product, dim_customer, dim_date + 3 aggregates (documented keys and grain)
        |------------------> [8 bias_detection]  representation, coverage, cancellations, time, cleaning impact
        |------------------> [9 privacy_scan]    PII scan of published text, identifier inventory, small cells
        v
 [7 validate_outputs] GX suites (115 expectations incl. bronze) + 13 reconciliation checks: critical / warning
        v
 [10 publish]  gates: bronze OK, outputs OK, no PII hits -> atomic publish + MANIFEST + LATEST pointer   (else BLOCK, nothing written)
        v
 [11 evidence_summary]  run_summary.json, reports/latest/
```

Task dependencies are enforced by Prefect futures (`flow.py`). `profile_source`, `bias_detection` and `privacy_scan` are leaf branches that may run concurrently with their siblings.
Retries: only I/O-bound `ingest` (2 retries, 2 s delay). Gate failures are deterministic and are never retried. On any failure the flow writes `run_status.json` (`FAILED`, failed task names, error class) and an audit event; publication is the last step, so a failed run publishes nothing.

## Mapping to the Module 2 technical architecture (layers carried over unchanged)

| Module 2 layer | Module 3 implementation | Production equivalent named in Modules 1-2 (DEPLOYMENT RECOMMENDATION) |
|---|---|---|
| Source | UCI Online Retail II CSV in `data/raw/` | Landing in Azure Data Lake Storage (raw zone) |
| Ingestion / orchestration | Prefect flow, `ingest` task | Azure Data Factory pipeline with a Copy activity; each Prefect task is one ADF activity |
| Storage zones | `raw`, `bronze`, `silver`, `staging`, `published` directories | ADLS Gen2 containers per zone with RBAC/ACLs |
| Preparation | pandas rules in `cleaning.py` / `transform.py` | Same Python in an ADF-triggered Databricks/Functions/Container job |
| Validation | Great Expectations 1.24.1 suites + reconciliation | Same suites in the pipeline job; failures alert Data and IT |
| Analytics layer | Parquet star schema + aggregates | Azure SQL / Synapse serverless over the curated zone |
| Presentation | Consumers listed per table in `catalog.py` | Power BI (executive, sales, customer, inventory dashboards) |
| Security / secrets | Env-var secret, read-only raw, audit events | Key Vault, RBAC, platform logs |
| Version control | Repository layout, tests, CI template | GitHub (Module 1) |

**Orchestration choice.** Module 2 names Azure Data Factory, a managed Azure service that cannot be executed locally or for free. To deliver an executable, reproducible workflow the DAG is implemented in Prefect (open source) and runs from one command or one Docker image. Task boundaries mirror ADF activities, so porting is mechanical; no Module 2 architectural layer is removed or replaced. Airflow was not needed because the existing architecture does not require it.

**Repository layout versus Module 1.** The Module 1 tree (`src/data/ingest.py`, `preprocess.py`, `tests/`, `configs/`, `docs/`, `reports/`) is retained in spirit: `src/retail_pipeline/` replaces `src/data/` for the pipeline stages; modelling folders (`features/`, `models/`, `evaluation/`, `dashboards/`, `notebooks/`) belong to later modules and are not created here.

## Outputs, consumers, refresh

| Table | Grain | Consumers |
|---|---|---|
| fact_sales_line | invoice line | analytics modelling; Power BI detail (restricted) |
| dim_product / dim_customer / dim_date | stock code / pseudonymised customer / day | all consumers |
| agg_daily_sales | day x country | Finance & leaders (executive), E-commerce & Operations (sales), exception alerts |
| agg_weekly_sku_demand | ISO week x stock code (sparse) | Inventory & Procurement, forecasting |
| agg_customer_rfm_base | pseudonymised customer | Marketing (RFM), churn / CLV models |

**Refresh frequency - two different things.**
* *Actual update frequency of the source:* none. The file is a static historical snapshot (1 Dec 2009 - 9 Dec 2011); re-running yields identical outputs.
* *Proposed pipeline schedule (PROPOSED, not deployed or executed):* daily at 02:00 UTC if a live transaction feed replaces the snapshot (`publish.proposed_schedule_cron`); until then, on demand. Aggregates would refresh on every run; the full fact on every run is acceptable at ~35 s for 1.07 M rows.

## Scalability and collaboration (consistent with the implemented architecture)

* **Measured today:** full run on 1,067,371 rows takes about 35-45 s on one machine, single-threaded pandas, peak memory a few GB (not profiled precisely).
* **Next steps if volume grows (PROPOSED):** partition parquet by `year_month` and process incrementally by invoice date; use Polars/DuckDB for the heavy groupbys; move to Spark on Databricks/Synapse above the single-machine limit; keep Great Expectations suites unchanged by validating per partition.
* **Idempotency:** a run reads only immutable bronze and writes only a new `run_id` folder; republishing the same inputs gives identical content hashes, so retries and backfills are safe.
* **Collaboration:** suites, rules and dictionary are plain files reviewed in pull requests; `scripts/build_docs.py` regenerates docs; tests run in CI (workflow template provided, not executed here); Prefect work pools or ADF triggers provide scheduling; `reports/latest/` gives reviewers the evidence for each change.
