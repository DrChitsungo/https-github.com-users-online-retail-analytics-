# CI evidence: GitHub Actions run #4

| Item | Value |
|---|---|
| Workflow | `.github/workflows/ci.yml` (name: ci), trigger: push |
| Run title | Fix repo layout: add hidden files, move reports, update Dockerfile #4 |
| Commit | `dfb67ea` on `main` |
| Result | Success, total duration 2m 4s (Mon 26 Oct 2026) |
| Job `test` | passed, 1m 7s: pinned install from `requirements.lock.txt`, `pytest` |
| Job `docker` | passed, 2m 1s: `docker build -t retail-pipeline .`, then `pytest` inside the image |
| Run page | https://github.com/DrChitsungo/https-github.com-users-online-retail-analytics-/actions/runs/40368853759 |

## What this shows
* The Dockerfile builds on a clean GitHub-hosted Linux runner with the pinned dependencies.
* The test suite passes both in a plain Python environment and inside the built image.

## What it does not show
* The pipeline was **not** run on the full Online Retail II file inside a container (the dataset is not in the repository and CI does not have it). The full-data runs (run-001, run-002) were executed in a Python virtual environment; see `fresh_venv_check.txt`, `reproducibility_check.json` and `reports/latest/`.
* The run summary showed two warnings and two notices (the runner reporting that Node.js 20 based actions are being run on Node.js 24). They do not affect the result.

Source: the run summary page as seen by the author; the per-step logs were not read by the assistant. Record added to the repository by the assistant from the run page contents supplied by the author.
