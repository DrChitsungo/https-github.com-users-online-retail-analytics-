# Module 5 requirements-to-evidence checklist and remaining limitations

The Module 5 brief, rubric, screenshots and referencing guidance were **not supplied**; this checklist is built from the written requirements in the task prompt. Anything the rubric might change is marked.

| # | Requirement | Artifact | Status | Note |
|---|---|---|---|---|
| 1 | 12-15 slide stakeholder presentation | `deck/Module5_Churn_Insights.pptx` | Done | 15 slides = 12 main + 3 appendix (the prompt's default when the rubric is unclear; **rubric not seen**) |
| 2 | Q&A backup as appendix slides in the same file | Slides 13-15; `docs/module5_technical_QA.md` | Done | |
| 3 | No recommendation or executive-summary slide | `scripts/verify_module5.py` (title check) | Done | Slide 11 gives implications and open questions only |
| 4 | Reuse the Module 4 model and API; no silent retraining | `models/churn_logreg_v1.0.0.*`; `src/churn_model/api.py` unchanged | Done | Model checksum shown in the dashboard and deck |
| 5 | One primary audience and decision context | Slides 1-3; evidence register | Done | Marketing and CRM managers (Module 1 tactical level; Model Card users) |
| 6 | Verified evidence base | `docs/module5_evidence_register.md` (15 rows); `scripts/verify_module5.py` (28 checks) | Done | Numbers are generated from `dashboard_evidence.json` |
| 7 | Score vs calibrated probability | Slides 3, 4, 10; dashboard Results | Done | Called a risk score; not recalibrated |
| 8 | Global explanation, 2-3 held-out examples, what-if | Slides 6-8; dashboard Results and Prediction | Done | 3 cases on the slide, 5 in the dashboard; selection rule documented; what-if uses live API |
| 9 | Fairness, privacy and ethics communication | Slides 9-10, 14; dashboard Fairness | Done, **requirement partly unmet** | No protected attributes in data; UK vs non-UK operational view only; FPR gap outside the Module 1 band; no fairness or compliance claim |
| 10 | Interactive dashboard (Streamlit or Dash) with five views | `dashboard/app.py` | Done | 18 tests; every view rendered in a browser |
| 11 | Ethical compliance view with fairness metrics | Dashboard "Fairness and ethics" | Done | |
| 12 | Live predictions call the actual Module 4 API; errors visible | `dashboard/dash_lib/core.py`; tests | Done locally | Never shows a stored score as a live one; verified in the assembled Space files in a fresh pinned virtualenv |
| 13 | API demonstration script | `scripts/api_demo.py`; `reports/evidence/api_demo_output.txt` | Done | 6 expectations and parity check, run against the local API |
| 14 | Deploy to Hugging Face Spaces or Streamlit Community Cloud | Hugging Face Docker Space (Bezzel/retail-churn-dashboard) | Done | Deployed by the author; first upload missed the model file, found from the container logs and corrected |
| 15 | Working live dashboard URL, independently verified | Slide 12; README | Verified 2026-10-31 | Opened in a separate browser: five views, live prediction (0.589 to 0.245) and 422 on invalid input all worked. Uptime and load untested |
| 16 | QR code for the verified deployment | `deck/qr_dashboard.png` | Done | Decodes to the verified URL |
| 17 | Existing GitHub repository updated | `github_upload_module5.zip` | Prepared, **not pushed** | Read-only access; the owner uploads. Do not treat as done until the CI run is green |
| 18 | README, env template, safe ignore rules | `README.md`, `.env.example`, `.gitignore` | Done | `.env.example` extended, not replaced |
| 19 | AI Disclosure Form per supplied requirements | `Nexford_AI_Disclosure_Form_MSDA_BChitsungo_Mod5_COMPLETED.docx` | Drafted | Module 5 form not supplied; adapted from the Module 4 form; fields marked `[AUTHOR TO CONFIRM]` need your own attestations |
| 20 | APA 7 references (Nexford style, confirmed by the author) | Slide 12; in-text citations on slides 6, 9, 10 | Done, partly verified | Full APA entries carried over from the Module 4 report list. Chen (2019) and Kamiran and Calders (2012) were checked in Module 4; Hardt, Lundberg, Mitchell and Weerts were not re-checked against publisher pages |
| 21 | Rendering and layout check | LibreOffice render of all 15 slides; `validate.py` passed | Done | Not opened in PowerPoint itself |

## Remaining limitations and unmet requirements

1. Live dashboard checked once on 2026-10-31; uptime, load and free-tier sleep behaviour are untested. The deployed About page still shows the older short reference list until `app/app.py` is re-uploaded.
2. Module 5 brief and rubric not seen (the author said to disregard the rubric); the 12 + 3 slide allocation is an interpretation. References are APA 7 as the author confirmed; four were not re-checked against publisher pages.
3. Protected-attribute fairness cannot be assessed (no such data); the non-UK false-alarm gap (+0.075) is unresolved; the instructor clarification request is unsent.
4. Business impact is unmeasured; every benefit statement is a hypothesis.
5. The 90-day churn window and 180-day lookback are proposed, not agreed with Marketing.
6. Test set scored twice plus exploratory runs (disclosed); one test window; no drift evidence.
7. The hosted API is internal to the Space, so the API demo script runs against a local copy of the same code; the hosted API was exercised only through the dashboard.
