"""Export the code-defined Great Expectations suites as reviewable JSON (gx/expectations/)."""
from pathlib import Path

from retail_pipeline import config, validation

root = Path(__file__).resolve().parents[1]
names = validation.export_suites(config.load_config(), root / "gx" / "expectations")
print(f"exported {len(names)} suites to gx/expectations/")
