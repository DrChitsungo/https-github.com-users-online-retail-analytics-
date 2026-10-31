# Requirements-to-evidence checklist (Module 4)

Status key: **Done** = built and checked; **Partial** = built with a stated gap; **Pending** = needs input I do not have. Nothing is marked done on the strength of intent.

| # | Requirement | Status | Evidence | Gap / note |
|---|---|---|---|---|
| 1 | Business need and defensible predictive task; target constructible; incomplete follow-up not labelled negative | Done | Validation Report §1–2; `configs/churn.yaml`; `tests/test_churn_model.py` (label and split tests) | Windows (90/180 days) are **PROPOSED**; Marketing agreement pending |
| 2 | Protected-attribute feasibility: state the gap, do not infer, do not present Country as protected | Done (gap stated) | Fairness Report preface; Validation Report §6 | Requirement itself **unmet** |
| 3 | Clarification request drafted, **not sent** | Done | `docs/instructor_clarification_request_DRAFT.md` | Student decides whether to send |
| 4 | Dataset audit, leakage controls, fit-on-train-only pipelines | Done | `src/churn_model/dataset.py`, `common.py`; leakage and imputer tests | |
| 5 | Evaluation protocol: baseline, untouched test, no tuning on test | Partial | Validation Report §3, §7; `selection.json` written before test | Test scored twice (iteration 1 and 2) plus exploratory mitigation looks: **disclosed** |
| 6 | MLflow set up before first experiment; real runs only | Done | `reports/mlflow_evidence/` (CSV exports, 2 UI screenshots) | One failed run and iteration-1 runs retained and tagged; no public MLflow link (local store) |
| 7 | Baseline + 2–3 candidates; CV search; imbalance handling in folds | Done | `train.py`; Validation Report §4 | |
| 8 | Metrics and labelled/captioned figures | Done | Report Tables 1–4, Figures 1–3; `reports/model/figures/` | |
| 9 | SHAP global and local | Done | `notebooks/shap_analysis.ipynb` (executed) | Rankings differ from LightGBM; flagged in report |
| 10 | Counterfactuals (verified; mutable/immutable; no protected changes) | Done | notebook §3; `explain.py` | Associational, not causal |
| 11 | Sensitivity analysis | Done | notebook §4; Report §5 | |
| 12 | Formal fairness analysis (DP, EO, DI, group sizes, uncertainty) | Partial | Fairness Metrics Report | Only UK vs non-UK (supplementary); protected-attribute analysis impossible with this data |
| 13 | Mitigation with before/after if material disparity | Done | Fairness Report §5 | Not adopted; disparity remains; no claim of elimination |
| 14 | Model Card with monitoring plan tied to Module 1 risk | Partial | `docs/MODEL_CARD.md` | Supplied Module 1 text has no numbered risk IDs; ties are to named risks (model bias, user resistance). Triggers PROPOSED |
| 15 | Serialised final model | Done | `models/churn_logreg_v1.0.0.joblib` + metadata | |
| 16 | FastAPI `POST /predict` (validation, identical preprocessing, version, invalid-input handling, no sensitive logging) | Done | `src/churn_model/api.py`; 18 API tests (of 27 churn tests; 91 tests in the full suite) incl. parity with stored test predictions | |
| 17 | Model Validation Report 1,800–2,200 words, captioned figures/tables | Partial | `reports/Model_Validation_Report.md/.docx` | Main text 1,987 words; 2,032 with headings; 2,162 with headings and captions (5 figures, 4 tables); about 2,440 if table cells are also counted. Appendices and references excluded. Submission brief says 1,800–2,200 but not how to count |
| 18 | SHAP notebook | Done | `notebooks/shap_analysis.ipynb` | |
| 19 | Repo-ready code, pinned deps, README, commands, verification | Partial | `requirements-ml.txt`, README Module 4 section, tests | Not pushed to GitHub; not a git checkout in the working environment |
| 20 | AI Disclosure Form | Drafted, awaiting learner sign-off | `Nexford_AI_Disclosure_Form_MSDA_BChitsungo_Mod4_COMPLETED.docx` (filled from the learner's own form; delivered separately) | Learner must confirm every statement is accurate (other AI tools used? Q6 edits?) before submitting; Report Appendix A points to it |
| 21 | Versions and results consistent across report, notebook, card, MLflow, artefact, API | Done | `scripts/verify_module4.py` (22 cross-artefact checks; log in `reports/evidence/module4_verification.txt`) | |
| 22 | Rubric and course details | Partial | Submission list received (report 1,800–2,200 words; Validation Report, SHAP notebook, Fairness Report, Model Card, MLflow link/screenshots, model file, FastAPI /predict, APA references) | Full grading rubric still not supplied |
| 23 | References in APA format | Done (verify) | Validation Report References section, with in-text citations | Checked against the publisher/UCI pages: Chen (2019) dataset DOI and creator; Kamiran & Calders (2012) title, authors, journal, volume, pages, DOI. NOT checked: Mitchell et al. DOI, Hardt et al. and Lundberg & Lee page numbers, Weerts et al., Pedregosa et al., Tabassi DOI, ICO URL. UCI's own citation year for Online Retail II differs (page lists a 2019 donation); confirm the year your style guide wants |
