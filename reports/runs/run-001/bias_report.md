# Bias / representation report

_Internal representation imbalance only; no demographic fairness claim is possible from this dataset._

## Key findings

- United Kingdom accounts for 92.0% of retained lines and 85.6% of gross sales revenue; effective number of countries = 1.2 of 43.
- 39 of 43 countries each hold under 1% of lines; 20 have fewer than 5 identified customers.
- Customer ID is present on 78.0% of retained lines and 93.5% of retained invoices (unidentified invoices are fewer but much larger); unidentified lines carry 13.5% of net revenue. Countries with flagged identification coverage: none.
- Cancellation invoices are 15.8% of retained invoices. Countries with flagged cancellation rates: Germany, EIRE, Netherlands, Switzerland.
- Partial reporting months: 2011-12; Q4 (Oct-Dec) holds 37.0% of gross sales revenue.
- Cleaning removes 3.21% of raw lines overall; removal rate is 6.50% for unidentified-customer lines vs 2.25% for identified. Countries whose share shifts beyond the band: none.

## Implications

- Aggregate KPIs, forecasts and segments are dominated by the United Kingdom; non-UK results rest on thin samples and should be reported with sample sizes or grouped.
- RFM, churn and lifetime-value models can only learn from identified customers; if unidentified purchasing differs, models describe a sub-population.
- Two annual cycles (December three) limit seasonality estimates; the final partial month must not be compared with full months.
- Cancellations cannot be linked to their original sale, so cancellation rates are invoice-level and not product-return rates.

## Mitigations

- Report all KPIs with group sample sizes; apply a minimum-n rule or group small countries (e.g. 'Other') before charting or modelling.
- Keep unidentified-customer transactions in revenue, product and demand analytics; restrict only customer-level models to identified customers and state this coverage.
- Flag partial months (dim_date.is_partial_month) and exclude them from month-over-month growth and seasonal fitting.
- Evaluate forecast and churn model errors by country group (Module 2 Fairlearn plan) once models exist; this pipeline stage only supplies the representation baseline.
- Re-run this suite on every refresh and review flagged groups at the AI Ethics Committee's monthly meeting (Module 1 governance).

## Limitations

- No external benchmark or population reference was available; reference = dataset's own overall rate and equal calendar coverage.
- Country is a business attribute; no demographic attributes exist, so demographic fairness is NOT assessed.
- Ratio-band thresholds are internal screening heuristics, chosen for documentation and review, not statistical or legal standards.

## Top countries (retained lines)

| Country | Lines | Share | Invoices | Identified customers | Thin | Small cell |
|---|---:|---:|---:|---:|:-:|:-:|
| United Kingdom | 950,526 | 92.01% | 42,779 | 5,357 |  |  |
| EIRE | 17,404 | 1.68% | 727 | 3 |  | Y |
| Germany | 16,679 | 1.61% | 1,035 | 107 |  |  |
| France | 13,557 | 1.31% | 709 | 93 |  |  |
| Netherlands | 5,017 | 0.49% | 227 | 22 | Y |  |
| Spain | 3,653 | 0.35% | 168 | 38 | Y |  |
| Switzerland | 3,124 | 0.30% | 111 | 22 | Y |  |
| Belgium | 2,961 | 0.29% | 172 | 29 | Y |  |
| Portugal | 2,471 | 0.24% | 106 | 23 | Y |  |
| Australia | 1,879 | 0.18% | 108 | 15 | Y |  |
| Channel Islands | 1,636 | 0.16% | 75 | 13 | Y |  |
| Italy | 1,472 | 0.14% | 80 | 17 | Y |  |

Full tables are in `bias_report.json`.
