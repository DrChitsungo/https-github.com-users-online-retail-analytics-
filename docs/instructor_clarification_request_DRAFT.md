# DRAFT, NOT SENT: clarification request for the instructor

**Status:** draft prepared for the student's review. It has not been sent to anyone.

**Subject:** BAN 6800 Module 4: guidance on protected attributes, fairness metrics and churn definition

Dear Professor [name],

I am completing the Module 4 predictive modelling assignment, a 90-day customer churn model on the Online Retail II data carried through Modules 1 to 3. The model, report, Model Card, fairness report, SHAP notebook, MLflow evidence and FastAPI service are complete. Before I submit, I would value your guidance on four points that I cannot settle from the data alone.

1. **Protected attributes.** The dataset contains no age, sex, ethnicity, disability or similar attribute, and I have not inferred any. Does the assignment require formal analysis of specific protected attributes? If so, which ones, and from which source?
2. **Supplementary grouping.** The only demographic-like field is country. I do not treat it as a protected attribute. May I report UK versus non-UK customers as a clearly labelled supplementary grouping, together with a customer-segment audit (tenure, spend and purchase-frequency tiers), and record the protected-attribute requirement as unmet for this dataset? Or would you prefer a different dataset, or a synthetic attribute clearly labelled as synthetic?
3. **Fairness metrics.** For a churn classifier where a positive prediction triggers a retention offer, which metrics does the rubric expect, for example demographic parity, equalised odds or disparate impact? I currently report all three with confidence intervals. On UK versus non-UK, the false-positive-rate gap is +0.075 (95% CI 0.009 to 0.145), outside the 10% band I set in Module 1. Two mitigation methods did not close it, so I did not adopt them and have disclosed this in the report.
4. **Churn definition.** Module 2 left the churn window to be agreed with Marketing. I agreed 90 days with a 180-day eligibility lookback with the Marketing Director on 1 November 2026. The Marketing Director confirmed it by email on 1 November 2026. Please confirm this is acceptable for the assignment.

I would also be grateful if you could share the grading rubric, which I do not have. I have completed the Nexford AI Disclosure Form and will submit it with the work.

Thank you for your time. I can resubmit or amend any part of the work once I have your guidance.

Kind regards,
Bezzel Chitsungo
MSc Data Analytics, Nexford University
eng.chitsungo@gmail.com
