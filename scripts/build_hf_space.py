"""Assemble the Hugging Face Space folder (and zip) from the repository sources. Run: python scripts/build_hf_space.py
Output: build/hf_space/ and build/hf_space.zip. Nothing is uploaded; see dashboard/README.md for the manual upload steps."""
import shutil, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "build" / "hf_space"
if OUT.exists(): shutil.rmtree(OUT)
(OUT / "src/churn_model").mkdir(parents=True); (OUT / "models").mkdir(); (OUT / "app").mkdir()
for f in ("README.md", "Dockerfile", "start.sh"): shutil.copy(ROOT / "dashboard/space" / f, OUT / f)
shutil.copytree(ROOT / "dashboard/space/.streamlit", OUT / ".streamlit"); shutil.copy(ROOT / "dashboard/requirements.txt", OUT / "requirements.txt")
shutil.copy(ROOT / "dashboard/app.py", OUT / "app/app.py"); shutil.copytree(ROOT / "dashboard/dash_lib", OUT / "app/dash_lib", ignore=shutil.ignore_patterns("__pycache__")); shutil.copytree(ROOT / "dashboard/data", OUT / "app/data")
for f in ("__init__.py", "api.py"): shutil.copy(ROOT / "src/churn_model" / f, OUT / "src/churn_model" / f)
for f in ("churn_logreg_v1.0.0.joblib", "churn_logreg_v1.0.0.metadata.json"): shutil.copy(ROOT / "models" / f, OUT / "models" / f)
z = ROOT / "build" / "hf_space.zip"
with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
    for p in sorted(OUT.rglob("*")):
        if p.is_file(): zf.write(p, p.relative_to(OUT))
print("built", OUT, "files:", sum(1 for p in OUT.rglob('*') if p.is_file()), "->", z)
