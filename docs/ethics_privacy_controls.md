# From commitments to controls: Ethical AI Charter and Privacy Plan

How each Module 1 / Module 2 commitment is turned into something that runs (or is explicitly not yet covered).
Status: **Implemented** (code + test/evidence), **Partial**, **Deployment** (needs platform), **Later** (needs models), **Org** (needs the organisation/DPO).

## Module 1 - Ethical AI Charter (s2.3 Fairness objectives, s3.1 oversight)

| Commitment | Implemented control | Evidence | Status |
|---|---|---|---|
| Compare outcome rates across groups to find disproportionate disadvantage | `bias.py` compares customer-identification and cancellation rates by country against the overall rate with Wilson 95% intervals | `reports/latest/bias_report.json` | Implemented for data representation; model outcome rates **Later** |
| Assess results outside acceptable ratio ranges | Ratio band 0.8-1.25 (internal screening heuristic) with minimum group size of 100 invoices; flags need ratio outside band AND CI excluding overall rate | `configs/pipeline.yaml` `bias:`; `tests/test_bias.py` | Implemented |
| Subgroup recall/error within 10% of overall | Pipeline supplies group sample sizes and thin-group flags so model evaluation can apply minimum-n rules | `country_representation.table` | **Later** (no models yet) |
| Examine country, address and payment variables for proxy effects | Only **Country** exists in the data; address and payment fields are absent (verified from the eight-field schema). Country is treated as a quasi-identifier and potential proxy: reported, never used to exclude records | `docs/data_dictionary.yaml`, `privacy_report.json` | Implemented to the extent the data allows |
| Corrective action when needed | Mitigations documented and tied to findings (min-n rule, grouping small countries, partial-month flag, identified-only scope for customer models) | `bias_report.md` | Partial (applied by downstream consumers) |
| Human review of major actions (credit terms, exclusions) | The pipeline makes **no** customer-level decisions; published data are descriptive inputs | `docs/governance.md` s2 | Implemented by design; enforcement downstream **Org** |
| AI Ethics Committee monthly review | `bias_report` and validation warnings are the review packs | `reports/latest/` | **Org** |
| Transparency / accountability | Reason codes for every non-retained row; lineage; manifests with run/rules/code identifiers | `cleaning_summary.json`, `docs/lineage.md`, `MANIFEST.json` | Implemented |

## Module 2 - Data Privacy Plan (s6.1)

| Lifecycle stage / commitment | Implemented control | Evidence | Status |
|---|---|---|---|
| Collection: ingest only required fields; record source and purpose | Exactly the eight source fields are read; source, provider and checksum recorded; purposes in governance doc | `ingestion_manifest.json` | Implemented |
| Collection: lawful basis, LIA, DPIA, marketing consent | Not decided by code | - | **Org** (DPO, Sprint 0) |
| Storage: raw and processed zones separated | `data/raw`, `bronze`, `silver`, `staging`, `published`, `reports`; raw/bronze read-only | directory layout, `ingest.py` | Implemented (directories) |
| Storage: encryption at rest/in transit, Azure RBAC least privilege, audit logging | Documented target; pipeline-level audit events implemented | `docs/governance.md` s3, s7 | **Deployment** (platform) / audit Partial |
| Preparation: Customer ID pseudonymised with a keyed hash before analysis; key held by Data and IT only | HMAC-SHA256 keyed pseudonym applied in the silver stage; raw ID dropped from every table after it; key from env var | `privacy.py`, `tests/test_privacy_audit.py`, fact `customer_key` regex gate | Implemented; custody **Deployment** |
| Modelling: models trained on pseudonymised data | Published S2 tables contain only `customer_key` | `validation` schema suites reject any raw-ID column | Implemented |
| Modelling: no raw data in GitHub; secrets in Key Vault; code review | `.gitignore` excludes `data/`, `.env`, run artefacts; `.env.example` has placeholders; env-var secret (Key Vault in production) | `.gitignore`, `tests/test_repo_hygiene.py` | Implemented / Key Vault **Deployment**; code review **Org** |
| Reporting: aggregated outputs, no individual identifiers on executive dashboards, row-level security | Aggregate tables (`agg_daily_sales`, `agg_weekly_sku_demand`) carry no customer fields; small-country cells reported | `privacy_report.json` (small-cell list) | Implemented for outputs; RLS **Deployment**; suppression rules **Org** |
| Archival/deletion: retention schedule with DPO, secure deletion, data-subject requests, breach procedure | Proposed schedule and procedures documented; nothing automated | `docs/governance.md` s5, s8 | **Proposed** / **Org** |

## What the data does and does not contain (from profiling and the privacy scan)

* **Direct identifiers present:** none found in the eight fields. Staff first names appeared in 71 raw ledger-style descriptions and are redacted.
* **Pseudonymous identifier:** `Customer ID` (22.77% missing) -> `customer_key`. Pseudonymised data are still personal data.
* **Quasi-identifiers:** Country, timestamp to the second, basket composition / purchase history. Small countries (fewer than 5 identified customers) are listed in `privacy_report.json`.
* **Sensitive data / protected characteristics:** none present and none inferred; demographic fairness cannot be assessed from this dataset.
