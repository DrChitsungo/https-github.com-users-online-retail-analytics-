# Data Dictionary

_Generated from `docs/data_dictionary.yaml`. Statistics marked (measured) describe the pinned source file._

Sensitivity: S0 none, S1 internal business, S2 pseudonymous personal data (restricted), S3 raw identifier (restricted zone only).

## Source: Online Retail II

- Provider: UCI Machine Learning Repository (dataset 502); Chen, D. (2019)
- Format: CSV, UTF-8 text, comma-delimited, header row, 1,067,371 data rows (measured)
- Grain: One invoice line (one product on one invoice)
- Actual update frequency of the source: Static historical snapshot, 2009-12-01 to 2011-12-09; no ongoing updates

| Field | Source type | Target type | Nullable | Definition | Constraints / observed | Sensitivity |
|---|---|---|---|---|---|---|
| Invoice | text | string | no | Invoice number; 6 digits. A leading 'C' marks a cancellation invoice; a leading 'A' marks a bad-debt accounting adjustment. | Regex ^[A-Za-z]?[0-9]{6}$ (critical). 'C' prefix on 19,494 rows / 8,292 invoices (measured); 'A' prefix on 6 rows. Cancellation invoice numbers do not match any original invoice number in the file (measured 0%), so cancellations cannot be linked to the sale they reverse. | S1 |
| StockCode | text | string | no | Product (SKU) code; 5 digits optionally followed by letters. Also holds non-merchandise ledger codes (POST, DOT, M, BANK CHARGES, ...). | Upper-cased and trimmed on ingestion (3,471 lowercase rows, measured). Merchandise patterns and non-merchandise patterns are listed in configs/pipeline.yaml. 62 distinct codes do not match the 5-digit pattern (measured); most are ledger lines, some are legitimate DCGS-series items. | S0 |
| Description | text | string | yes | Free-text product name; occasionally a ledger memo. | 4,382 missing rows (0.41%, measured), all with price 0 and no customer. Trimmed, whitespace-collapsed, personal-name patterns redacted. 213,035 rows carry leading/trailing whitespace; 1,212 stock codes have more than one description (measured). 71 raw rows contain a staff first name after 'adjustment by/found by' (measured) - redacted. | S1 |
| Quantity | text | int64 | no | Units on the line. Negative on cancellations. | Integer. Negative allowed ONLY on 'C' invoices in published data. 22,950 negative rows raw: 19,493 on C invoices, 3,457 on non-C invoices (stock adjustments, price 0, no customer) (measured). Range -80,995 to 80,995 (measured); the extreme pair is a sale and its cancellation on the same product. | S0 |
| InvoiceDate | text | datetime | no | Invoice timestamp to the second (retailer local time, timezone not stated in source). | Format YYYY-MM-DD HH:MM:SS (critical). 2009-12-01 07:45:00 to 2011-12-09 12:50:00 (measured). December 2011 is a partial month. Timestamps are quasi-identifying in combination with Country and basket contents. One backward step in file order (2010-12-09 -> 2010-12-01 at row 525,461) marks a block boundary. | S1 |
| Price | text | float64 | no | Unit price in GBP (currency stated by dataset documentation, not in the file). | Decimal, up to 3 decimals. Zero on 6,202 rows; negative on 5 rows ('Adjust bad debt'); maximum 38,970 on a 'Manual' line (measured). Published lines require price > 0.  | S1 |
| Customer ID | text | Int64 (transient; never persisted outside bronze) | yes | Retailer's customer number, stored as a float-like string (e.g. 13085.0). | 243,007 missing rows (22.77%, measured); 5,942 distinct values. Regex ^[0-9]+(\.0+)?$ when present. Pseudonymous identifier. Replaced by customer_key (HMAC-SHA256) before any table leaves the bronze zone. Missing values are retained as unidentified transactions. | S3 |
| Country | text | string | no | Customer's country as recorded by the retailer. | 43 distinct values (measured); includes 'Unspecified' (756 rows) and 'European Community'. United Kingdom = 981,330 rows (measured). Quasi-identifier for small countries. Only group attribute available for representation checks. | S1 |

## Disposition and reason codes

Every raw row has exactly one disposition (retained / quarantined / excluded) and a reason code. Stored in the restricted silver zone.

- `disposition` (string): retained | quarantined | excluded
- `reason_code` (string): OK or a code from cleaning.REASON_ORDER (EXC_DUP_OVERLAP, EXC_NON_MERCHANDISE, QRN_*)

## Output: `fact_sales_line`

Retained invoice lines (sales and cancellations) with business measures. Grain - one invoice line.

- Primary key: line_id
- Consumers: Data engineering / analytics modelling layer; Power BI semantic model (detail drill-through, restricted)
- Sensitivity note: Pseudonymous (customer_key) - restricted access

| Column | Type | Nullable | Key | Derived | Definition | Sensitivity |
|---|---|---|---|---|---|---|
| line_id | string | no | PK | yes | Invoice number + '-' + 4-digit ordinal of the line within its invoice in source row order; deterministic unique key. | S1 |
| raw_row_id | int64 | no |  | no | Source CSV row position (traceability). | S1 |
| invoice_no | string | no |  | yes | Invoice trimmed and upper-cased. | S1 |
| stock_code | string | no | FK->dim_product.stock_code | yes | Merchandise stock code, upper-cased. | S0 |
| invoice_ts | datetime | no |  | yes | Parsed invoice timestamp. | S1 |
| invoice_date | datetime | no | FK->dim_date.date | yes | Invoice date at midnight. | S1 |
| quantity | int64 | no |  | yes | Units; non-zero; negative only on cancellation invoices. | S0 |
| unit_price | float64 | no |  | yes | Unit price GBP, greater than 0 and at most 10,000 (configured). | S1 |
| line_revenue | float64 | no |  | yes | quantity x unit_price rounded to 4 dp; negative for cancellations. | S1 |
| is_cancellation | bool | no |  | yes | True when the invoice number starts with 'C'. | S0 |
| customer_key | string | yes | FK->dim_customer.customer_key | yes | 32-hex keyed HMAC-SHA256 pseudonym of Customer ID; null when Customer ID is missing. Pseudonymous, not anonymous. | S2 |
| customer_identified | bool | no |  | yes | True when customer_key is present. | S0 |
| country | string | no |  | yes | Country, trimmed. | S1 |
| source_block | int8 | no |  | yes | 1 or 2: which side of the single backward step in InvoiceDate (file order) the row sits on. INFERRED; the CSV does not record worksheet names. | S0 |
| is_exact_duplicate_within_source | bool | no |  | yes | Row is identical on all eight raw fields to an earlier retained row. Retained and flagged (may be a legitimate repeated scan). | S0 |

## Output: `dim_product`

One row per merchandise stock code present in the fact table.

- Primary key: stock_code
- Consumers: Inventory and Procurement; E-commerce and Operations (merchandising); Forecasting models
- Sensitivity note: Business data; free text scrubbed of personal-name patterns

| Column | Type | Nullable | Key | Derived | Definition | Sensitivity |
|---|---|---|---|---|---|---|
| stock_code | string | no | PK | yes | Merchandise stock code. | S0 |
| description | string | no |  | yes | Most frequent upper-cased description (ties alphabetical); personal-name patterns redacted. | S1 |
| n_description_variants | int64 | no |  | yes | Distinct upper-cased descriptions seen for the code. | S0 |
| first_sold_date | datetime | yes |  | yes | First date with a non-cancelled line. | S1 |
| last_sold_date | datetime | yes |  | yes | Last date with a non-cancelled line. | S1 |
| n_lines | int64 | no |  | yes | Retained lines (sales and cancellations). | S0 |
| median_unit_price | float64 | yes |  | yes | Median unit price over non-cancelled lines. | S1 |

## Output: `dim_customer`

One row per pseudonymised customer present in the fact table.

- Primary key: customer_key
- Consumers: Marketing (RFM/segmentation); Churn and lifetime-value models
- Sensitivity note: Pseudonymous - restricted access

| Column | Type | Nullable | Key | Derived | Definition | Sensitivity |
|---|---|---|---|---|---|---|
| customer_key | string | no | PK | yes | Keyed pseudonym (see fact_sales_line.customer_key). | S2 |
| country_primary | string | no |  | yes | Most frequent country over the customer's lines (ties alphabetical). | S2 |
| n_countries | int64 | no |  | yes | Distinct countries seen for the customer (13 customers have more than one in the raw data; measured). | S2 |
| first_purchase_date | datetime | yes |  | yes | First non-cancelled purchase date. | S2 |
| last_purchase_date | datetime | yes |  | yes | Last non-cancelled purchase date. | S2 |
| n_sales_invoices | int64 | no |  | yes | Distinct non-cancellation invoices. | S2 |
| n_cancellation_invoices | int64 | no |  | yes | Distinct cancellation invoices. | S2 |

## Output: `dim_date`

One row per calendar day between the first and last retained invoice date.

- Primary key: date
- Consumers: All reporting and forecasting consumers
- Sensitivity note: None

| Column | Type | Nullable | Key | Derived | Definition | Sensitivity |
|---|---|---|---|---|---|---|
| date | datetime | no | PK | yes | Calendar day. | S0 |
| year | int64 | no |  | yes | Calendar year. | S0 |
| month | int64 | no |  | yes | Calendar month 1-12. | S0 |
| iso_year | int64 | no |  | yes | ISO year. | S0 |
| iso_week | int64 | no |  | yes | ISO week 1-53. | S0 |
| week_start | datetime | no |  | yes | Monday of the ISO week. | S0 |
| day_of_week | int64 | no |  | yes | 0 = Monday ... 6 = Sunday. | S0 |
| is_partial_month | bool | no |  | yes | True when the month is not fully inside the observed window (December 2011). | S0 |

## Output: `agg_daily_sales`

Daily sales and cancellations by country. Grain - one calendar day x country.

- Primary key: invoice_date, country
- Consumers: Business leaders and Finance (executive dashboard); E-commerce and Operations (sales dashboard); Exception alerts
- Sensitivity note: Aggregated; small-country cells need suppression rules before wide sharing

| Column | Type | Nullable | Key | Derived | Definition | Sensitivity |
|---|---|---|---|---|---|---|
| invoice_date | datetime | no | PK FK->dim_date.date | yes | Invoice date. | S1 |
| country | string | no | PK | yes | Country. | S1 |
| sales_invoices | int64 | no |  | yes | Distinct non-cancellation invoices. | S0 |
| sale_lines | int64 | no |  | yes | Non-cancellation lines. | S0 |
| units_sold | int64 | no |  | yes | Units on non-cancellation lines. | S0 |
| gross_sales_revenue | float64 | no |  | yes | Sum of line_revenue on non-cancellation lines. | S1 |
| cancellation_invoices | int64 | no |  | yes | Distinct cancellation invoices. | S0 |
| cancellation_lines | int64 | no |  | yes | Cancellation lines. | S0 |
| units_cancelled | int64 | no |  | yes | Absolute units on cancellation lines. | S0 |
| cancellation_revenue | float64 | no |  | yes | Sum of line_revenue on cancellation lines (zero or negative). | S1 |
| net_revenue | float64 | no |  | yes | gross_sales_revenue + cancellation_revenue. | S1 |

## Output: `agg_weekly_sku_demand`

Weekly demand by product. Grain - one ISO week (Monday start) x stock code; sparse, weeks with no lines are absent.

- Primary key: week_start, stock_code
- Consumers: Inventory and Procurement (weekly SKU forecasts, reorder support); Demand forecasting models
- Sensitivity note: Aggregated business data

| Column | Type | Nullable | Key | Derived | Definition | Sensitivity |
|---|---|---|---|---|---|---|
| week_start | datetime | no | PK | yes | Monday of the ISO week. | S0 |
| stock_code | string | no | PK FK->dim_product.stock_code | yes | Stock code. | S0 |
| units_sold | int64 | no |  | yes | Units on non-cancellation lines. | S0 |
| gross_sales_revenue | float64 | no |  | yes | Revenue on non-cancellation lines. | S1 |
| n_sales_invoices | int64 | no |  | yes | Distinct non-cancellation invoices. | S0 |
| units_cancelled | int64 | no |  | yes | Absolute units on cancellation lines. | S0 |
| cancellation_revenue | float64 | no |  | yes | Revenue on cancellation lines (zero or negative). | S1 |
| net_units | int64 | no |  | yes | units_sold - units_cancelled. | S0 |

## Output: `agg_customer_rfm_base`

Inputs for RFM segmentation per pseudonymised customer. Grain - one customer. Recency is measured to the snapshot date (last observed date + 1 day).

- Primary key: customer_key
- Consumers: Marketing (RFM segments, campaign design); Churn and lifetime-value models
- Sensitivity note: Pseudonymous - restricted access

| Column | Type | Nullable | Key | Derived | Definition | Sensitivity |
|---|---|---|---|---|---|---|
| customer_key | string | no | PK FK->dim_customer.customer_key | yes | Keyed pseudonym. | S2 |
| first_purchase_date | datetime | yes |  | yes | First non-cancelled purchase date. | S2 |
| last_purchase_date | datetime | yes |  | yes | Last non-cancelled purchase date. | S2 |
| frequency_invoices | int64 | no |  | yes | Distinct non-cancellation invoices. | S2 |
| monetary_gross | float64 | no |  | yes | Sum of line_revenue on non-cancellation lines. | S2 |
| monetary_net | float64 | no |  | yes | Sum of line_revenue including cancellations. | S2 |
| n_cancellation_invoices | int64 | no |  | yes | Distinct cancellation invoices. | S2 |
| recency_days | Int64 | yes |  | yes | snapshot_date - last_purchase_date in days; null if the customer has no non-cancelled purchase. | S2 |
| snapshot_date | datetime | no |  | yes | Last observed invoice date + 1 day (data-derived, deterministic). | S0 |
