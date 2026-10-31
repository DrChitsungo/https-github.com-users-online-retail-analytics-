# Module 5 technical Q&A (backup for questions)

Every figure comes from `dashboard/data/dashboard_evidence.json` (built from the recorded Module 4 outputs). Slide references are to `deck/Module5_Churn_Insights.pptx`.

**1. What exactly does the model predict?** For a currently active, identified customer on a prediction date T: whether there will be no sales invoice in the following 90 days. Eligibility: at least one sales invoice in the 180 days before T. Both windows are PROPOSED, not agreed with Marketing (slide 3).

**2. Which information does it use, and can it see the future?** Eighteen behavioural features computed only from invoices before T. Automated tests change every invoice dated on or after T and confirm the features do not change, and confirm the label flips when a future purchase is added (slide 13).

**3. How was it validated?** Time-ordered splits (train Jun-Dec 2010, validation Mar-Apr 2011, test Aug-Sep 2011) with a 90-day purge. Four-fold expanding-window cross-validation with a three-month purge and 25 random-search draws, scored on ROC-AUC. Preprocessing is fitted inside each fold.

**4. Why logistic regression?** A selection rule fixed in advance: highest validation AUC; if a more interpretable model is within 0.005 AUC, prefer it; then a fairness gate. LightGBM (0.768) and random forest (0.769) were statistically indistinguishable from the logistic regression (0.765) on test.

**5. Is 0.765 AUC good enough?** It is a clear improvement over a rule ("longest-silent first", 0.663) and the intervals do not overlap (0.750-0.781 vs 0.646-0.680). It is a ranking aid, not a precise predictor.

**6. Why does it flag 67.6% of customers?** The threshold (0.314) maximises F1 on validation data, where 57% of customers lapsed. On the test period only 42% lapsed, so the same threshold over-flags. Slide 5 shows shorter lists, for example the top 20% (precision 70%, recall 33%). The list size is a business choice.

**7. Are the scores probabilities?** They are called risk scores. The mean score on test (0.425) is close to the lapse rate (0.418), but the model was not recalibrated and the lapse rate moved between periods, so scores are for ranking, not guaranteed frequencies.

**8. Was the test set touched more than once?** Yes, and it is disclosed: iteration 1 (AUC 0.767) and iteration 2 (0.765) after a collinearity problem was found without reference to test scores, plus exploratory mitigation runs.

**9. What drives predictions?** Purchase frequency (1.04), tenure (0.40), spend (0.33), product breadth (0.19), recency (0.12), purchase regularity (0.08), cancellations (0.05), as average absolute SHAP in log-odds. These are associations, not causes. A LightGBM cross-check agrees on 3 of its top 5 features, so individual rankings are somewhat model-dependent.

**10. Why SHAP and not LIME?** SHAP's LinearExplainer is exact for a linear model and consistent between global and local views. LIME was not run.

**11. How were the five example cases chosen?** By a deterministic rule: typical flagged churner, typical retained customer, most confident false positive, least confident false negative, and the case nearest the threshold. Two are errors on purpose.

**12. How does the what-if work and what does it not show?** It adds 0 to 6 invoices at the customer's own average order value, sets when the latest purchase happened, keeps counts and revenue windows nested and recomputes the recency-to-gap ratio, using the Module 4 counterfactual logic. Tenure, product breadth, gap statistics, cancellations and country are held fixed. It shows model sensitivity, not a causal effect.

**13. Why not DiCE or Alibi?** The mutable space is 36 scenarios, so a direct grid search that is re-scored through the same pipeline is simpler and fully verifiable. DiCE can restrict features too; the choice was about the size of the space.

**14. Which groups were assessed for fairness, and why?** UK vs non-UK customers, because country is the only demographic-like field. It is not a protected attribute. The data contains no age, sex, ethnicity or similar attribute and none was inferred. The protected-attribute requirement cannot be assessed with this data.

**15. What are the fairness results?** Disparate impact 1.039 (0.963-1.122), within 0.80-1.25. Flag-rate gap +0.026 (-0.025 to +0.081). True-positive gap -0.012 (-0.070 to +0.048), within 10% of overall. False-positive (false-alarm) gap +0.075 (0.009-0.145); ratio to overall 1.127, outside the Module 1 band 0.90-1.10. Non-UK n = 532, UK n = 5,002.

**16. What mitigation was tried?** Fairlearn ThresholdOptimizer (equalised odds) and Kamiran-Calders reweighing. Test-period false-alarm gaps were 0.080 and 0.086 against 0.075 unmitigated; group thresholds also cut recall to 0.755. Neither was adopted. The test numbers are exploratory because the disparity was first seen on test data.

**17. Is the model fair or legally compliant?** This work makes no such claim. Results are described as within or outside the project's stated thresholds, which are governance bands from Modules 1 and 2, not legal tests.

**18. How does the dashboard call the API, and is it the same model?** The dashboard sends model-ready features to `/predict` of the Module 4 FastAPI service. In the Hugging Face Space both run in one container, with the API bound to the loopback interface. The API loads the same `churn_logreg_v1.0.0.joblib`; tests assert parity with the serialised model and with the stored evaluation scores (within 0.002 after privacy rounding).

**19. What if the API is down?** The dashboard shows a visible error and produces no score. It never substitutes a stored or simulated prediction.

**20. What data is public?** Aggregate evaluation results, five rounded example profiles without identifiers or dates, and the 3 KB model file. No customer-level records.

**21. What is not yet known?** Any operational or financial effect of using the scores; the cost of a false alarm; whether the non-UK gap persists on newer data; whether a 90-day window suits the retailer; behaviour after deployment (no drift evidence).
