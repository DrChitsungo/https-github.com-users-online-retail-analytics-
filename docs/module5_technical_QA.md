# Module 5 technical Q&A (backup for questions)

Every figure comes from `dashboard/data/dashboard_evidence.json` (built from the recorded Module 4 outputs). Slide references are to `deck/Module5_Churn_Insights.pptx`.

**1. What exactly does the model predict?** For an identified customer on a prediction date T: whether there will be no sales invoice in the following 90 days. Eligibility: the customer's first sales invoice is at least 180 days before T. Both rules were agreed with the Marketing Director on 1 November 2026 (confirmed by email from the Marketing Director; slide 3).

**2. Which information does it use, and can it see the future?** Eighteen behavioural features computed only from invoices before T. Automated tests change every invoice dated on or after T and confirm the features do not change, and confirm the label flips when a future purchase is added (slide 13).

**3. How was it validated?** Time-ordered splits (train Jun-Dec 2010, validation Mar-Apr 2011, test Aug-Sep 2011) with a 90-day purge. Four-fold expanding-window cross-validation with a three-month purge and 25 random-search draws, scored on ROC-AUC. Preprocessing is fitted inside each fold.

**4. Why logistic regression?** A selection rule fixed in advance: highest validation AUC; if a more interpretable model is within 0.005 AUC, prefer it; then a fairness gate. On test, LightGBM (0.806) and random forest (0.816) were statistically indistinguishable from the logistic regression (0.810). An earlier run in which random forest was selected was caused by a data-preparation error (missing product counts imputed instead of set to zero); it was corrected and the whole pipeline rerun, and the rule then selected logistic regression.

**5. Is 0.810 AUC good enough?** It is a clear improvement over a rule ("longest-silent first", 0.757) (95% interval for the model 0.798-0.821). But much of it comes from customers who have been silent for 180 days or more (54% of test rows): the model flags 99.9% of them, and the AUC inside that group is 0.655. Among customers who also bought in the prior 180 days the AUC is 0.768. It is a ranking aid, not a precise predictor.

**6. Why does it flag 80.9% of customers?** The threshold (0.345) maximises F1 on validation data. Test churn is 60% and the model's precision is 0.71, a lift of about 1.18 over the base rate, so the default list is long and not very selective. Slide 5 shows shorter lists, for example the top 20% (precision 90%, recall 30%). The list size is a business choice.

**7. Are the scores probabilities?** They are called risk scores. The mean score on test (0.571) is below the lapse rate (0.603), and the model was not recalibrated, so scores are for ranking, not guaranteed frequencies.

**8. Was the test set touched more than once?** Yes, and it is disclosed: four times. Iteration 1 (AUC 0.767) and iteration 2 (0.765) under the earlier eligibility rule, a run under the Marketing rule that was discarded because of the data-preparation error, and the final run (0.810), plus exploratory mitigation, segment and subset checks.

**9. What drives predictions?** By group, purchase frequency (0.47), spend (0.26), product breadth (0.14), purchase regularity (0.12), cancellations (0.07), recency (0.06) and tenure (0.05), as average absolute SHAP in log-odds. These are associations, not causes. A LightGBM cross-check agrees on 2 of its top 5 features (rank correlation 0.28), so individual rankings are model-dependent.

**10. Why SHAP and not LIME?** SHAP's LinearExplainer is exact for a linear model and consistent between global and local views. LIME was not run.

**11. How were the five example cases chosen?** By a deterministic rule: typical flagged churner, typical retained customer, most confident false positive, least confident false negative, and the case nearest the threshold. Two are errors on purpose.

**12. How does the what-if work and what does it not show?** It adds 0 to 6 invoices at the customer's own average order value, sets when the latest purchase happened, keeps counts and revenue windows nested and recomputes the recency-to-gap ratio, using the Module 4 counterfactual logic. Tenure, product breadth, gap statistics, cancellations and country are held fixed. It shows model sensitivity, not a causal effect. With the latest purchase 90 days old, neither Case A (0.734 to 0.382) nor Case C (0.862 to 0.597) falls below the 0.345 threshold within six invoices.

**13. Why not DiCE or Alibi?** The mutable space is 36 scenarios, so a direct grid search that is re-scored through the same pipeline is simpler and fully verifiable. DiCE can restrict features too; the choice was about the size of the space.

**14. Which groups were assessed for fairness, and why?** UK vs non-UK customers, because country is the only demographic-like field. It is not a protected attribute. The data contains no age, sex, ethnicity or similar attribute and none was inferred. The protected-attribute requirement cannot be assessed with this data.

**15. What are the fairness results?** Disparate impact 0.967 (0.910-1.016), within 0.80-1.25. Flag-rate gap -0.027 (-0.073 to +0.013). True-positive gap -0.009 (-0.039 to +0.015), within 10% of overall. False-positive (false-alarm) gap -0.024 (-0.103 to +0.051); ratio to overall 0.963, inside the Module 1 band 0.90-1.10. Non-UK n = 715, UK n = 8,228. All intervals include zero, so this is not evidence of equal treatment. On validation the false-alarm ratio was 0.903, only just inside the band.

**16. What mitigation was tried?** Fairlearn ThresholdOptimizer (equalised odds) and Kamiran-Calders reweighing. No band was breached on test, so neither was needed or adopted. Group thresholds cut recall from 0.953 to 0.880 and raised the equalised-odds difference from 0.024 to 0.047; reweighing changed little (0.027). Test numbers are exploratory. A non-UK false-alarm gap of +0.075 seen under the earlier eligibility rule was not reproduced, but it is not claimed to be eliminated.

**17. Is the model fair or legally compliant?** This work makes no such claim. Results are described as within or outside the project's stated thresholds, which are governance bands from Modules 1 and 2, not legal tests.

**18. How does the dashboard call the API, and is it the same model?** The dashboard sends model-ready features to `/predict` of the Module 4 FastAPI service. In the Hugging Face Space both run in one container, with the API bound to the loopback interface. The API loads the same `churn_logreg_v1.0.0.joblib`; tests assert parity with the serialised model and with the stored evaluation scores (within 0.002 after privacy rounding).

**19. What if the API is down?** The dashboard shows a visible error and produces no score. It never substitutes a stored or simulated prediction.

**20. What data is public?** Aggregate evaluation results, five rounded example profiles without identifiers or dates, and the 3 KB model file. No customer-level records.

**21. What is not yet known?** Any operational or financial effect of using the scores; the cost of a false alarm; whether UK and non-UK error rates stay close on newer data; how the agreed 90-day window and 180-day eligibility rule suit the retailer in practice; whether long-silent customers should be a separate group; behaviour after deployment (no drift evidence).

**22. Did you test fairness on anything other than UK vs non-UK?** Yes, as a clearly labelled supplementary customer-segment audit: tertiles of tenure, spend and purchase frequency, with cut-offs fixed on the training snapshots. These are behavioural segments, not demographic and not protected. The fixed threshold flags 100% of customers with two or fewer invoices, so inside that tier the flag does not separate lapsers from stayers, while in the highest-frequency tier the model catches 69.4% of lapsers. It is exploratory and descriptive (a further look at the test period), the Module 1 bands are not applied to it, and it supports a recommendation that Marketing review the threshold by segment rather than any claim of fairness.

**23. What exactly do you say about protected attributes?** Protected attributes as defined by the Equality Act 2010 and the assignment brief are not present in Online Retail II and were not inferred. Therefore a formal protected-attribute fairness analysis is not possible on this dataset. The requirement is recorded as unmet due to a data limitation. No synthetic protected attribute was created and no other dataset was used.

