# Data governance framework

Scope: the Retail Analytics Decision Support Platform data pipeline (Module 3), built on the Module 1 Ethical AI Charter
(fairness, transparency, privacy, accountability) and the Module 2 Data Privacy Plan. Every control below is labelled:

* **IMPLEMENTED** - exists in this repository and was exercised in the recorded runs/tests.
* **DEPLOYMENT RECOMMENDATION** - requires the organisation's platform (Azure RBAC, Key Vault, storage policies); not built here.
* **PROPOSED POLICY** - a value or rule for the organisation (e.g. the DPO) to confirm; no project requirement fixes it.

## 1. Roles (PROPOSED role assignment - to be confirmed by the organisation)

| Role | Proposed holder (from Module 1 stakeholders) | Accountabilities |
|---|---|---|
| Data owner | Business leaders and Finance (CFO as accountable executive) | Approves purposes, approves access to restricted zones, accepts residual risk |
| Data protection officer | DPO (AI Ethics Committee member) | Lawful basis, DPIA, retention schedule, incident decisions, data-subject requests |
| Data steward | Data and IT / data & analytics lead | Owns the Data Dictionary, validation suites, reason codes, rules changes |
| Pipeline service identity | `svc-retail-pipeline` (configurable via `PIPELINE_ACTOR`) | Only identity that reads bronze and writes silver/published |
| Analyst / consumer | Marketing, Inventory & Procurement, E-commerce & Operations | Use published tables for the permitted purposes below |
| AI Ethics Committee | CFO, DPO, data & analytics leaders (Module 1 s3.1) | Monthly review of `bias_report` outputs and validation warnings |

## 2. Permitted and prohibited uses

Permitted (Module 2 purpose limitation): demand forecasting, customer segmentation (RFM), retention/churn analysis, and aggregate reporting.
Prohibited: re-identifying customers; joining `customer_key` to external personal data; exporting restricted-zone tables; using Country as a proxy to
exclude or disadvantage customers; fully automated credit-term or exclusion decisions (Module 1 requires human review).

## 3. Storage zones and access (zone separation IMPLEMENTED as directories; access control is a DEPLOYMENT RECOMMENDATION)

| Zone | Path | Contents | Sensitivity | Proposed access |
|---|---|---|---|---|
| Raw | `data/raw/` | Original CSV, made read-only on ingestion | S3 (raw Customer ID) | Pipeline service + named engineers approved by the data owner |
| Bronze | `data/bronze/<sha12>/` | All-text parquet copy + `raw_row_id`, content-addressed, read-only | S3 | As raw |
| Silver | `data/runs/<run_id>/silver/` | Typed, classified rows; **customer_key only**; quarantine and excluded rows with reason codes | S2 | Pipeline + data stewards |
| Staging | `data/runs/<run_id>/staging/` | Candidate outputs before gates | S2 | Pipeline |
| Published | `data/published/<run_id>/` | Gated outputs + `MANIFEST.json` | `fact_sales_line`, `dim_customer`, `agg_customer_rfm_base` S2; other tables S1/S0 | Aggregates: all stakeholders; S2 tables: Marketing/analytics on need-to-know |
| Reports | `reports/` | Profiling, validation, bias, privacy, audit logs (no records, no identifiers) | S1 | Project team |

Implemented: raw and bronze files are made read-only; processing never writes into raw; published output is written to a temp folder and renamed atomically only after all gates pass.
Deployment recommendation: ADLS Gen2 containers per zone with Azure RBAC/ACLs, encryption at rest and TLS in transit (Module 2 Storage controls), Power BI row-level security.

## 4. Pseudonymisation and key custody (IMPLEMENTED; custody is a DEPLOYMENT RECOMMENDATION)

* `customer_key` = HMAC-SHA256(secret, Customer ID), truncated to 32 hex characters. Deterministic for a given secret, so customers remain joinable across runs.
* The secret is read only from the environment variable `CUSTOMER_KEY_SECRET` (>= 32 characters, enforced). It is never written to configs, logs, reports or Git. Tests assert the audit log never contains it.
* `key_id` (8 hex chars, derived by HMAC of a constant) is recorded in manifests so the key version is traceable without revealing the key.
* This is **pseudonymous data, not anonymous data**. Anyone holding the secret or the raw IDs can re-link; country/time/basket patterns are quasi-identifying. The published S2 tables are therefore treated as personal data.
* Rotation (PROPOSED): generate a new secret, reprocess from bronze, publish a new run, retire the old key; downstream joins must use the new `key_id`.
* Production: store the secret in Azure Key Vault and inject it as an environment variable (Module 2 specifies Key Vault).

## 5. Retention and deletion (PROPOSED POLICY - Module 2 leaves the schedule to be agreed with the DPO; none is automated)

| Data | Proposed retention | Notes |
|---|---|---|
| Raw / bronze | Life of the project, then secure deletion | Historical snapshot; restricted |
| Silver / staging | 30 days after a successful publish | Rebuildable from bronze |
| Quarantine / excluded rows | 90 days | Needed to review rules |
| Published tables | `publish.proposed_retention_days` = 730 in `configs/pipeline.yaml` | Value is a placeholder for DPO decision |
| Audit logs | 12 months | Needed for incident review |

Deletion / data-subject requests: NOT IMPLEMENTED. Proposed approach: the data owner supplies the raw Customer ID, the steward computes its `customer_key` with the live secret, removes it from published/silver tables, and re-runs the pipeline with an exclusion rule. Azure Storage lifecycle-management policies are the recommended mechanism for time-based deletion.

## 6. Versioning and change control

* IMPLEMENTED: every run records `run_id`, `rules_version`, `rules_hash` (hash of the full configuration), `code_hash` (hash of all pipeline modules), `key_id`, source SHA-256 and a deterministic `build_id`; every published table carries a content hash. Identical inputs, configuration, code and key produce identical content hashes (verified, see `reports/evidence/reproducibility_check.json`).
* IMPLEMENTED: Data Dictionary (`docs/data_dictionary.yaml`) is validated by tests against the real output schemas, so documentation cannot silently drift.
* PROPOSED: pull-request review for any change to `configs/pipeline.yaml`, `docs/data_dictionary.yaml` or a validation suite; `CODEOWNERS` naming the data steward; tag a release when `rules_version` changes.

## 7. Audit logging

* IMPLEMENTED: every pipeline-managed read, write, transformation, validation and publication emits a structured JSON event (`audit_events.jsonl`): run id, UTC timestamp, actor/service, operation, dataset, row counts, outcome, rules version/hash, code hash. Events contain metadata only; the logger rejects secrets, identifier-like strings, long strings and structured records (tested).
* LIMIT: this log only covers access made **through the pipeline**. Reads of files by people or other tools need storage/platform audit controls (e.g. Azure Storage diagnostic logs, Entra ID sign-in logs) - DEPLOYMENT RECOMMENDATION.

## 8. Incident handling (PROPOSED procedure)

1. **Detect:** validation gate failure, audit-log anomaly, unexpected file access (platform logs), or a report of exposed data.
2. **Contain:** revoke access to the affected zone; if `customer_key` data or the secret may be exposed, rotate the secret and unpublish affected runs.
3. **Assess:** DPO determines whether personal data is involved and the risk to individuals; check `audit_events.jsonl` and platform logs for scope.
4. **Notify:** where a personal-data breach is likely to risk individuals' rights, the DPO decides on notifying the ICO (UK GDPR requires notification within 72 hours where feasible) and affected individuals.
5. **Remediate and review:** fix root cause, add a validation rule or test, record the lesson in the RAID log and review at the AI Ethics Committee.

## 9. Implemented versus recommended - summary

| Area | Implemented here | Needs the organisation |
|---|---|---|
| Immutable raw + checksums | Read-only raw/bronze, pinned SHA-256, manifest | Immutable storage (e.g. Azure immutable blob policy) |
| Pseudonymisation | HMAC keyed pseudonym, secret from env | Key Vault, custody, rotation |
| PII scrubbing/scan | Name patterns redacted, scans in privacy report, gate on published text | Periodic review of patterns |
| Validation gates | 115 expectations + reconciliation, critical gate | Alerting/ownership of failures |
| Audit logging | Pipeline events | Platform access logs, SIEM |
| Roles / RBAC | Documented roles | Azure RBAC, Power BI RLS |
| Retention / deletion | Proposed schedule only | DPO decision, lifecycle policies, DSAR process |
| Lawful basis, DPIA, LIA | Not in scope | DPO (Module 2 Sprint 0) |
