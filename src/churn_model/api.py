"""FastAPI service for the churn model.  Run:  PYTHONPATH=src uvicorn churn_model.api:app --port 8000

Contract: the caller sends MODEL-READY customer features (computed from the customer's sales-invoice history strictly BEFORE the prediction date;
see docs/model_feature_spec.md). The service does not accept customer identifiers or raw invoice lines, applies the same fitted preprocessing used in
training (median imputation, log1p, scaling) and returns the probability, the flag at the documented threshold and the model version.
Privacy: request bodies are never logged; only a request id, status code and latency are.
"""
from __future__ import annotations
import json, logging, os, time, uuid
from pathlib import Path
from typing import Optional
import joblib, pandas as pd
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(os.environ.get("CHURN_MODEL_PATH", ROOT / "models" / "churn_logreg_v1.0.0.joblib"))
META_PATH = MODEL_PATH.with_suffix(".metadata.json")
log = logging.getLogger("churn_api")

_pipe = joblib.load(MODEL_PATH); META = json.loads(META_PATH.read_text()); FEATURES = META["feature_order"]; THRESHOLD = META["threshold"]; VERSION = META["model_version"]


class CustomerFeatures(BaseModel):
    """One currently active, identified customer at one prediction date. All counts/amounts use sales invoices dated before the prediction date."""
    model_config = ConfigDict(extra="forbid")
    recency_days: float = Field(ge=0, le=180, description="Days since the last sales invoice (customer must have bought within the last 180 days)")
    tenure_days: float = Field(ge=0, le=5000, description="Days since the first sales invoice")
    n_inv_all: int = Field(ge=1, le=100000, description="Sales invoices in all history")
    n_inv_30: int = Field(ge=0, le=100000, description="Sales invoices in the last 30 days")
    n_inv_90: int = Field(ge=0, le=100000, description="Sales invoices in the last 90 days")
    n_inv_prev90: int = Field(ge=0, le=100000, description="Sales invoices 91-180 days before the prediction date")
    rev_all: float = Field(ge=0, le=1e8, description="Sales revenue, all history (GBP)")
    rev_90: float = Field(ge=0, le=1e8); rev_180: float = Field(ge=0, le=1e8)
    n_products_all: int = Field(ge=1, le=100000); n_products_180: int = Field(ge=0, le=100000)
    avg_units_per_inv: float = Field(ge=0, le=1e7)
    mean_gap_days: Optional[float] = Field(default=None, ge=0, le=5000, description="Mean days between invoices; null if undefined (single invoice)")
    std_gap_days: Optional[float] = Field(default=None, ge=0, le=5000)
    recency_over_gap: Optional[float] = Field(default=None, ge=0, le=100000)
    n_cancel_all: int = Field(ge=0, le=100000); cancel_ratio: float = Field(ge=0, le=1)
    is_single_invoice: Optional[int] = Field(default=None, ge=0, le=1, description="Optional; derived as (n_inv_all == 1) and must agree if supplied")

    @model_validator(mode="after")
    def _consistency(self):
        if self.tenure_days < self.recency_days: raise ValueError("tenure_days must be >= recency_days")
        if not (self.n_inv_30 <= self.n_inv_90 <= self.n_inv_all): raise ValueError("require n_inv_30 <= n_inv_90 <= n_inv_all")
        if self.n_inv_90 + self.n_inv_prev90 > self.n_inv_all: raise ValueError("n_inv_90 + n_inv_prev90 must not exceed n_inv_all")
        if not (self.rev_90 <= self.rev_180 <= self.rev_all): raise ValueError("require rev_90 <= rev_180 <= rev_all")
        if self.n_products_180 > self.n_products_all: raise ValueError("n_products_180 must not exceed n_products_all")
        if self.n_inv_90 + self.n_inv_prev90 < 1: raise ValueError("customer must have at least one invoice in the last 180 days (eligibility rule)")
        derived = int(self.n_inv_all == 1)
        if self.is_single_invoice is not None and self.is_single_invoice != derived: raise ValueError("is_single_invoice must equal (n_inv_all == 1)")
        self.is_single_invoice = derived
        return self


class Prediction(BaseModel):
    request_id: str; model_version: str; churn_probability: float; flagged_high_churn_risk: bool; decision_threshold: float
    imputed_fields: list[str]; notes: list[str]


app = FastAPI(title="Retail churn model API", version=VERSION, description="Predicts 90-day churn risk for currently active, identified customers. Advisory only; human review required.")


@app.middleware("http")
async def _access_log(request: Request, call_next):
    rid = str(uuid.uuid4()); t0 = time.time(); request.state.rid = rid
    resp = await call_next(request); log.info("request_id=%s path=%s status=%s ms=%.1f", rid, request.url.path, resp.status_code, (time.time() - t0) * 1000)   # never the body
    resp.headers["X-Request-ID"] = rid; return resp


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, exc: RequestValidationError):
    # report field names and rule messages only; never echo submitted values
    errs = [{"field": ".".join(str(x) for x in e["loc"] if x != "body") or "body", "problem": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "invalid input", "errors": errs})


@app.get("/health")
def health(): return {"status": "ok", "model_version": VERSION}


@app.get("/model")
def model_info():
    return {"model_version": VERSION, "task": META["task"], "threshold": THRESHOLD, "features": FEATURES, "validation": META["validation"], "test": META["test"],
            "intended_use": META["intended_use"], "not_for": META["not_for"], "dataset_hash": META["dataset_hash"]}


@app.post("/predict", response_model=Prediction)
def predict(x: CustomerFeatures, request: Request):
    row = pd.DataFrame([x.model_dump()])[FEATURES].astype(float)
    imputed = [c for c in META["features_allowed_missing"] if pd.isna(row.loc[0, c])]
    p = float(_pipe.predict_proba(row)[0, 1])
    notes = ["Advisory score for human-reviewed retention planning; not for automated decisions about individuals."]
    if imputed: notes.append("Missing gap statistics were replaced with training medians; supply them whenever they are defined.")
    return Prediction(request_id=request.state.rid, model_version=VERSION, churn_probability=round(p, 6), flagged_high_churn_risk=p >= THRESHOLD, decision_threshold=THRESHOLD, imputed_fields=imputed, notes=notes)
