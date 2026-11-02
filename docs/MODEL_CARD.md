# Model Card: `churn_logreg` v1.0.0

Format follows Mitchell et al. (2019). Every figure comes from `models/churn_logreg_v1.0.0.metadata.json` and `reports/model/*.json`.

## 1. Model details
| Item | Value |
|---|---|
| Name / version | `churn_logreg` / 1.0.0 (artefact `models/churn_logreg_v1.0.0.joblib`) |
| Type | scikit-learn Pipeline: median imputer → log1p → standard scaler → logistic regression (`C=0.0014`, no class weighting) |
| Developer | Bezzel Chitsungo, MSc Data Analytics, Nexford University (BAN 6800), with AI assistance (Claude, Anthropic); see Validation Report Appendix A |
| Date | 2 Nov 2026 (rebuilt under the eligibility rule agreed with Marketing on 1 Nov 2026) |
| Training data | Module 3 published fact table, prediction dates Jun–Dec 2010 (11,699 customer-snapshot rows, 2,714 customers) |
| Dataset hash / code hash / config hash | `4a1207e03b61b5ca` / `b67892ac5408478a` / `c6f4eb455aeac10b` |
| Registry | MLflow Model Registry `retail-churn-logreg`, version 3, alias `champion` (record: `reports/mlflow_evidence/model_registry.json`). The alias marks the version the API serves; it is not production approval |
| Tracking | MLflow experiment `retail-churn-90d`; validation run `c9e4e15238904308afa33cb9d7622d9a`; test run `fd728799ac5d4d8e8d4e24914d41fa77`; runs with other dataset hashes are superseded |
| Versions | Python 3.13.17, scikit-learn 1.9.1, pandas 3.0.5, numpy 2.5.3 |
| Licence / contact | Coursework prototype; no licence granted. Contact: the author via the course submission |

## 2. Intended use
* **Task:** rank identified customers with at least 180 days of purchase history by probability of **no sales invoice in the next 90 days** (90-day window and 180-day history rule agreed with the Marketing Director on 1 November 2026, confirmed by email).
* **Churn definition (agreed):** Churn definition agreed with Marketing: churn = no sales invoice (purchase) in the 90 days following the observation date, with the customer eligible only if they had at least 180 days of prior history (first sales invoice at least 180 days before the observation date). Agreed with the Marketing Director on 1 November 2026 (confirmed by email from the Marketing Director, 1 November 2026).
* **Users:** Marketing and CRM analysts preparing human-reviewed retention campaigns.
* **Out of scope:** automated decisions about individuals (credit terms, exclusions, pricing); guest/unidentified customers; customers with fewer than 180 days of history (outside the agreed eligibility rule); inferring any personal characteristic; use outside this retailer's data.

## 3. Factors and data
* 18 behavioural features (recency, tenure, invoice counts and revenue over windows, product breadth, purchase-gap statistics, cancellations). Country, customer key and snapshot date are not predictors.
* **Protected attributes as defined by the Equality Act 2010 and the assignment brief are not present in Online Retail II and were not inferred. Therefore a formal protected-attribute fairness analysis is not possible on this dataset. Requirement recorded as unmet due to data limitation.**
* UK vs non-UK is recorded as `geographic_grouping_for_robustness_check` (an operational grouping, **not** a protected characteristic). Tenure, spend and purchase-frequency tiers are a `customer-segment audit` (behavioural, not demographic). No synthetic protected attribute was created.
* Customers are pseudonymised (HMAC-SHA256). Pseudonymous is not anonymous; treat inputs as personal data.
* Three gap features are missing for single-invoice customers (21–26% of rows) and are imputed with training medians.

## 4. Evaluation
Time-ordered splits with a 90-day purge: train Jun–Dec 2010, validation Mar–Apr 2011, test Aug–Sep 2011 (8,943 rows, 4,538 customers, churn rate 0.603).

| Metric (threshold 0.345328) | Validation | Test (95% CI, customer-clustered bootstrap) |
|---|---|---|
| ROC-AUC | 0.805 | 0.810 (0.798–0.821) |
| PR-AUC | 0.848 | 0.844 (0.827–0.857) |
| Precision | 0.755 | 0.710 (0.695–0.722) |
| Recall | 0.910 | 0.953 (0.946–0.958) |
| F1 | 0.825 | 0.813 (0.803–0.822) |
| Brier | 0.181 | 0.172 |

Baselines on test: prevalence AUC 0.500; recency rule AUC 0.757 (0.744–0.769). Candidates LightGBM (0.806) and random forest (0.816) were statistically indistinguishable; logistic regression was selected by a pre-declared interpretability rule after passing the validation fairness gate. At a churn rate of 0.603 the model flags 80.9% of customer-snapshots, so precision 0.710 is a lift of 1.18 over flagging everyone. 54% of test rows are customers with no purchase in the prior 180 days, for whom the flag is almost uninformative (AUC 0.655, flag rate 0.999); among customers who also bought in the prior 180 days AUC is 0.768 (0.750–0.786), precision 0.523 and recall 0.836 (Validation Report §4).

## 5. Explanations
Global SHAP (log-odds): purchase frequency (0.47), spend (0.26), product breadth (0.14), regularity (0.12), cancellations (0.07), recency (0.06), tenure (0.05). Five local cases chosen by a deterministic rule; counterfactuals restricted to mutable behaviour and verified by re-scoring; sensitivity to noise, missingness and recency shifts is small (|ΔAUC| ≤ 0.001). See `notebooks/shap_analysis.ipynb`. SHAP and counterfactuals describe the model, not causes of churn.

## 6. Fairness (supplementary operational grouping only)
| Test metric | UK (8,228 rows) | Non-UK (715 rows) | Non-UK vs UK |
|---|---|---|---|
| Selection rate | 0.812 | 0.785 | DI 0.967 (band 0.80–1.25: met) |
| TPR | 0.953 | 0.944 | −0.009 (CI −0.039, 0.015) |
| FPR | 0.594 | 0.570 | −0.024 (CI −0.103, 0.051); ratio to overall 0.963, inside ±10% band |

Validation gate passed narrowly (non-UK FPR ratio 0.903 against a 0.90 limit); mitigations (equalised-odds thresholds, reweighing) were exploratory, were not needed on test and were not adopted. **The protected-attribute fairness requirement is unmet** (no such attributes) and awaits instructor clarification. This card does not claim the model is fair or unbiased.

**Customer-segment audit (behavioural, not protected; exploratory).** On the test predictions, the fixed threshold flags every customer in the lowest purchase-frequency tier (flag rate 1.000, false-alarm rate 1.000) and lowest-spend tier (flag rate 1.000, false-alarm rate 0.998), while in the highest-frequency tier it catches 0.694 of lapsers. A single threshold therefore behaves very differently by customer type; Marketing should review it by segment. Details: Fairness Metrics Report, Section 7. **Disclosure:** the higher non-UK false-alarm rate seen under the earlier eligibility rule (+0.075) was not reproduced under the agreed rule (difference −0.024, CI −0.103 to 0.051), but the group is small and the disparity is not claimed to be eliminated; the mitigations were not adopted (group thresholds cut recall from 0.953 to 0.880).

## 7. Ethical considerations and risks
Model bias (a principal concern in Module 1; owner AI Ethics Committee per the Module 2 RAID log; the register in the supplied Module 1 text has no numbered IDs, so IDs must be mapped by the author) and user resistance. A false-positive flag leads to an unnecessary offer; a false negative (missed churner, e.g. a high-value customer who left) is a lost-retention opportunity. Country may act as a proxy; the ablation shows the model does not need it. Predictions are probabilities for ranking, not statements about individuals.

## 8. Caveats and limitations
1. The 90-day churn window and the 180-day history rule were agreed with the Marketing Director on 1 November 2026 (confirmed by email from the Marketing Director). A different window or rule would change every metric. The rule admits long-lapsed customers (54% of test rows), which raises prevalence to 0.60.
2. Test set scored four times (two iterations under the earlier eligibility rule, one discarded run with a data error, and the final run) plus exploratory mitigation, segment and subset checks; disclosed in the Validation Report §7.
3. Churn rate differs by period (0.47 training, 0.62 validation, 0.60 test); the F1-optimal threshold flags 80.9% of customers on test; set the operating point by campaign capacity.
4. Weaker on customers unseen in training (AUC 0.772 against 0.816).
5. One test window; no external validation; no drift evidence yet.
6. Probabilities are not recalibrated.

## 9. Monitoring plan (PROPOSED; to be agreed with Marketing and the AI Ethics Committee)
| What | How often | Trigger for review | Linked risk |
|---|---|---|---|
| Input drift (PSI or similar) on the 18 features; share of missing gap features | weekly, by the caller on its scored batches (the API logs no bodies) | PSI > 0.2 on any top-5 feature, or missing share outside 20–50% | Model bias / drift |
| Flag rate | each campaign cycle | more than 10 points from pilot value (≈ 81%) | Model bias; resource waste |
| AUC and calibration on matured months | monthly, 90-day lag | AUC < 0.70 or mean predicted vs observed churn differing by > 0.05 | Model performance |
| UK vs non-UK DI, TPR, FPR with intervals | quarterly | DI outside 0.80–1.25, or TPR/FPR outside ±10% of overall for two consecutive reviews | Model bias (AI Ethics Committee) |
| Human override and complaint log | continuous | any complaint citing country or nationality | User resistance / fairness |
| Retraining | at least every 6 months or on any trigger above | n/a | n/a |

Owners: Marketing (use), Data and IT (pipeline and API), AI Ethics Committee (fairness review). Triggers are PROPOSED values, not agreed controls.

## 10. How to use
`POST /predict` returns probability, flag, threshold and model version; see `README.md` and `docs/model_feature_spec.md`. Version 1.0.0 is for a supervised pilot only.
