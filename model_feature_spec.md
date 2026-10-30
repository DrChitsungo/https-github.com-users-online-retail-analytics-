# Churn model: feature specification and caller responsibilities

**Prediction date T.** All features use *sales* invoices (not cancellations) of an identified customer dated **strictly before T**. The caller must only
send customers with at least one sales invoice in the 180 days before T. Cancellation invoices attributed to the customer before T feed the two cancellation features only.
`recency_days` etc. are whole days between T and the invoice date. Revenue is in GBP (the dataset currency).

| Field | Definition |
|---|---|
| recency_days | T minus date of latest sales invoice (0-180) |
| tenure_days | T minus date of first sales invoice |
| n_inv_all / n_inv_30 / n_inv_90 | sales invoices in all history / last 30 / last 90 days |
| n_inv_prev90 | sales invoices 91-180 days before T |
| rev_all / rev_90 / rev_180 | sum of line revenue over all history / last 90 / last 180 days |
| n_products_all / n_products_180 | distinct stock codes bought in all history / last 180 days |
| avg_units_per_inv | mean units per sales invoice |
| mean_gap_days / std_gap_days | mean / standard deviation of days between consecutive invoice dates; null if undefined (single invoice; std needs two gaps) |
| recency_over_gap | recency_days / mean_gap_days; null if mean gap is undefined or 0 |
| n_cancel_all / cancel_ratio | cancellation invoices before T; n_cancel_all / (n_inv_all + n_cancel_all) |
| is_single_invoice | optional; 1 if n_inv_all == 1 (derived by the service) |

Excluded on purpose: customer identifiers, Country and any grouping field (evaluation only), calendar month/season, and anything dated on or after T.
The service rejects impossible combinations (e.g. n_inv_30 > n_inv_90) with a 422 that names the field but never echoes the submitted values.
