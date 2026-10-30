# Model Card: `churn_logreg` v1.0.0

Format follows Mitchell et al. (2019). Every figure comes from `models/churn_logreg_v1.0.0.metadata.json` and `reports/model/*.json`.

## 1. Model details
| Item | Value |
|---|---|
| Name / version | `churn_logreg` / 1.0.0 (artefact `models/churn_logreg_v1.0.0.joblib`) |
| Type | scikit-learn Pipeline: median imputer → log1p → standard scaler → logistic regression (`C=0.376`, balanced class weights) |
| Developer | Bezzel Chitsungo, MSc Data Analytics, Nexford University (BAN 6800), with AI assistance (Claude, Anthropic); see Validation Report Appendix A |
| Date | 26 Oct 2026 |
| Training data | Module 3 published fact table, prediction dates Jun–Dec 2010 (20,584 customer-snapshot rows, 4,225 customers) |
| Dataset hash / code hash / config hash | `794106a862ace0f8` / `258a93f8e40c9463` / `af26659fdee2cf73` |
| Tracking | MLflow experiment `retail-churn-90d`; validation run `58bcfae5b9ad4569ad79747717d42cb2`; test run `8e8e21abe6bd4867b0b2e2a67056b591` |
| Versions | Python 3.13.17, scikit-learn 1.9.1, pandas 3.0.5, numpy 2.5.3 |
| Licence / contact | Coursework prototype; no licence granted. Contact: the author via the course submission |

## 2. Intended use
* **Task:** rank identified customers who bought in the last 180 days by probability of **no sales invoice in the next 90 days** (both windows **PROPOSED**, pending Marketing agreement).
* **Users:** Marketing and CRM analysts preparing human-reviewed retention campaigns.
* **Out of scope:** automated decisions about individuals (credit terms, exclusions, pricing); guest/unidentified customers; customers inactive for more than 180 days; inferring any personal characteristic; use outside this retailer's data.

## 3. Factors and data
* 18 behavioural features (recency, tenure, invoice counts and revenue over windows, product breadth, purchase-gap statistics, cancellations). Country, customer key and snapshot date are not predictors.
* **No protected attributes exist in the data and none were inferred.** UK vs non-UK is an operational grouping used for supplementary analysis only.
* Customers are pseudonymised (HMAC-SHA256). Pseudonymous is not anonymous; treat inputs as personal data.
* Three gap features are missing for single-invoice customers (26–43% of rows) and are imputed with training medians.

## 4. Evaluation
Time-ordered splits with a 90-day purge: train Jun–Dec 2010, validation Mar–Apr 2011, test Aug–Sep 2011 (5,534 rows, 2,968 customers, churn rate 0.418).

| Metric (threshold 0.313903) | Validation | Test (95% CI, customer-clustered bootstrap) |
|---|---|---|
| ROC-AUC | 0.775 | 0.765 (0.750–0.781) |
| PR-AUC | 0.781 | 0.670 (0.646–0.698) |
| Precision | 0.696 | 0.545 (0.525–0.565) |
| Recall | 0.905 | 0.881 (0.866–0.896) |
| F1 | 0.787 | 0.674 (0.656–0.690) |
| Brier | 0.198 | 0.193 |

Baselines on test: prevalence AUC 0.500; recency rule AUC 0.663 (0.646–0.680). Candidates LightGBM (0.768) and random forest (0.769) were statistically indistinguishable; logistic regression was selected by a pre-declared interpretability rule.

## 5. Explanations
Global SHAP (log-odds): purchase frequency (1.04), tenure (0.40), spend (0.33), product breadth (0.19), recency (0.12). Five local cases chosen by a deterministic rule; counterfactuals restricted to mutable behaviour and verified by re-scoring; sensitivity to noise, missingness and recency shifts is small (|ΔAUC| ≤ 0.006). See `notebooks/shap_analysis.ipynb`. SHAP and counterfactuals describe the model, not causes of churn.

## 6. Fairness (supplementary operational grouping only)
| Test metric | UK (5,002 rows) | Non-UK (532 rows) | Non-UK vs UK |
|---|---|---|---|
| Selection rate | 0.673 | 0.699 | DI 1.039 (band 0.80–1.25: met) |
| TPR | 0.882 | 0.871 | −0.012 (CI −0.070, 0.048) |
| FPR | 0.520 | 0.595 | **+0.075 (CI 0.009, 0.145); ratio to overall 1.127, outside ±10% band** |

Validation gate passed; mitigations (equalised-odds thresholds, reweighing) did not close the gap on test and were not adopted. **The protected-attribute fairness requirement is unmet** (no such attributes) and awaits instructor clarification. This card does not claim the model is fair or unbiased.

## 7. Ethical considerations and risks
Model bias (a principal concern in Module 1; owner AI Ethics Committee per the Module 2 RAID log; the register in the supplied Module 1 text has no numbered IDs, so IDs must be mapped by the author) and user resistance. A false-positive flag leads to an unnecessary offer; a false negative (missed churner, e.g. a high-value customer who left) is a lost-retention opportunity. Country may act as a proxy; the ablation shows the model does not need it. Predictions are probabilities for ranking, not statements about individuals.

## 8. Caveats and limitations
1. Churn and lookback windows are PROPOSED.
2. Test set scored in two iterations and in exploratory mitigation runs; disclosed in the Validation Report §7.
3. Prevalence shifted 0.57 (validation) → 0.42 (test), so the F1-optimal threshold flags 67.6% of customers; set the operating point by campaign capacity.
4. Weaker on customers unseen in training (AUC 0.688).
5. One test window; no external validation; no drift evidence yet.
6. Probabilities are not recalibrated.

## 9. Monitoring plan (PROPOSED; to be agreed with Marketing and the AI Ethics Committee)
| What | How often | Trigger for review | Linked risk |
|---|---|---|---|
| Input drift (PSI or similar) on the 18 features; share of missing gap features | weekly, by the caller on its scored batches (the API logs no bodies) | PSI > 0.2 on any top-5 feature, or missing share outside 20–50% | Model bias / drift |
| Flag rate | each campaign cycle | more than 10 points from pilot value (≈ 67%) | Model bias; resource waste |
| AUC and calibration on matured months | monthly, 90-day lag | AUC < 0.70 or mean predicted vs observed churn differing by > 0.05 | Model performance |
| UK vs non-UK DI, TPR, FPR with intervals | quarterly | DI outside 0.80–1.25, or TPR/FPR outside ±10% of overall for two consecutive reviews | Model bias (AI Ethics Committee) |
| Human override and complaint log | continuous | any complaint citing country or nationality | User resistance / fairness |
| Retraining | at least every 6 months or on any trigger above | n/a | n/a |

Owners: Marketing (use), Data and IT (pipeline and API), AI Ethics Committee (fairness review). Triggers are PROPOSED values, not agreed controls.

## 10. How to use
`POST /predict` returns probability, flag, threshold and model version; see `README.md` and `docs/model_feature_spec.md`. Version 1.0.0 is for a supervised pilot only.
