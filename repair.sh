set -e
# 1. put the report folders where the docs expect them (reports/...)
mkdir -p reports
git mv latest reports/latest
git mv runs reports/runs
git mv evidence reports/evidence
git mv source_profile.json reports/source_profile.json
# 2. remove placeholder / stray files
git rm -q -r --ignore-unmatch repair.sh retail-pipeline-repo.zip ".gitignore." configs/configs.yaml
# 3. add the hidden files that the browser upload skipped
mkdir -p data && touch data/.gitkeep
cat > .gitignore <<'EOF_GITIGNORE'
# secrets and local environment
.env
*.env
!.env.example

# data zones: raw, bronze, runs and published data must never be committed
data/
!data/.gitkeep

# run artefacts (the curated evidence under reports/evidence and reports/latest IS committed; per-run folders are not)
reports/runs/
.prefect/
gx/uncommitted/

# python
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/
*.egg-info/
.ipynb_checkpoints/
EOF_GITIGNORE
cat > .env.example <<'EOF_ENV_EXAMPLE'
# Copy to .env (never commit .env). Values below are placeholders, NOT real secrets.
# Generate a real secret:  python -c "import secrets; print(secrets.token_hex(32))"
CUSTOMER_KEY_SECRET=replace-with-at-least-32-random-characters
# Optional: label recorded as the 'actor' in audit events (a service identity, not a person)
PIPELINE_ACTOR=svc-retail-pipeline
# Optional overrides
# RETAIL_PIPELINE_HOME=/app
# PREFECT_LOGGING_LEVEL=INFO
EOF_ENV_EXAMPLE
cat > .dockerignore <<'EOF_DOCKERIGNORE'
.git
.env
data/
reports/runs/
.prefect/
__pycache__/
.pytest_cache/
.venv/
EOF_DOCKERIGNORE
# 3b. write the real workflow (the existing ci.yml only contains its own file name)
mkdir -p .github/workflows
cat > .github/workflows/ci.yml <<'EOF_CI'
# Provided as a repository-ready workflow; it has NOT been executed by the author until a run appears in the repo's Actions tab.
# Tests use hand-written fixtures, so the real dataset is not needed.
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install -c requirements.lock.txt -r requirements.txt pytest==9.1.1
      - run: PYTHONPATH=src python -m pytest
  docker:
    # Builds the Dockerfile and runs the test suite inside the image (no dataset or secret needed).
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t retail-pipeline .
      - run: docker run --rm --entrypoint python -e PREFECT_HOME=/tmp/.prefect retail-pipeline -m pytest
EOF_CI
# 4. let the Docker image contain the files the tests read
sed -i 's#^COPY pytest.ini ./#COPY pytest.ini ./\n\# files read by tests/test_repo_hygiene.py\nCOPY .gitignore .env.example Dockerfile README.md ./#' Dockerfile
# 5. commit and push
git add -A
git add -f data/.gitkeep
git commit -m "Fix repo layout: add hidden files, move reports, update Dockerfile"
git push
