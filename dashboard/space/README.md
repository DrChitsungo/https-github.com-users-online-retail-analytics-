---
title: Retail Churn Model Dashboard
emoji: 📊
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
short_description: Stakeholder dashboard for a 90-day retail churn model
---

# Retail churn model: stakeholder dashboard (BAN 6800, Module 5)

Interactive dashboard for the Module 4 90-day customer churn model (logistic regression v1.0.0), written for Marketing and CRM managers.
It shows verified results, explanations, a what-if explorer that calls the model's FastAPI service, and a fairness and ethics view.

- **Audience:** Marketing and CRM managers planning human-reviewed retention campaigns.
- **Data:** aggregate evaluation results only. No customer identifiers or customer-level records are stored here.
- **Limits:** no protected attributes exist in the data; the UK vs non-UK view is an operational comparison, not a fairness or compliance certification. The 90-day churn window is proposed, not agreed.
- **Source code and documents:** https://github.com/DrChitsungo/https-github.com-users-online-retail-analytics-

The container runs two processes: the Module 4 FastAPI service (bound to the container's loopback interface only) and this Streamlit app, which calls it.
