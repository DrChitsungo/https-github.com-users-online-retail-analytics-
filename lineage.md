# Lineage

```
online_retail_II.csv (raw, immutable, read-only)
  -> bronze/raw_strings.parquet        all-text copy + raw_row_id, content-addressed by sha256
  -> silver/row_disposition|retained|quarantine|excluded.parquet   typed, rule-classified, Customer ID pseudonymised
  -> silver/fact_sales_line.parquet     business transformations (line_revenue, is_cancellation, line_id)
  -> staging/*.parquet                  dimensions, fact and aggregates
  -> published/<run_id>/*.parquet       only after all validation + privacy gates pass
```

## Raw field to output field

| Raw field | Output columns derived from it |
|---|---|
| Invoice | fact_sales_line.line_id, fact_sales_line.invoice_no, fact_sales_line.is_cancellation, fact_sales_line.is_exact_duplicate_within_source, dim_product.first_sold_date, dim_product.last_sold_date, dim_product.n_lines, dim_customer.first_purchase_date, dim_customer.last_purchase_date, dim_customer.n_sales_invoices, dim_customer.n_cancellation_invoices, agg_daily_sales.sales_invoices, agg_daily_sales.sale_lines, agg_daily_sales.cancellation_invoices ... (20 columns) |
| StockCode | fact_sales_line.stock_code, fact_sales_line.is_exact_duplicate_within_source, dim_product.stock_code, agg_weekly_sku_demand.stock_code (4 columns) |
| Description | fact_sales_line.is_exact_duplicate_within_source, dim_product.description, dim_product.n_description_variants (3 columns) |
| Quantity | fact_sales_line.quantity, fact_sales_line.line_revenue, fact_sales_line.is_exact_duplicate_within_source, agg_daily_sales.units_sold, agg_daily_sales.gross_sales_revenue, agg_daily_sales.units_cancelled, agg_daily_sales.cancellation_revenue, agg_daily_sales.net_revenue, agg_weekly_sku_demand.units_sold, agg_weekly_sku_demand.gross_sales_revenue, agg_weekly_sku_demand.units_cancelled, agg_weekly_sku_demand.cancellation_revenue, agg_weekly_sku_demand.net_units, agg_customer_rfm_base.monetary_gross ... (15 columns) |
| InvoiceDate | fact_sales_line.invoice_ts, fact_sales_line.invoice_date, fact_sales_line.source_block, fact_sales_line.is_exact_duplicate_within_source, dim_product.first_sold_date, dim_product.last_sold_date, dim_customer.first_purchase_date, dim_customer.last_purchase_date, dim_date.date, dim_date.year, dim_date.month, dim_date.iso_year, dim_date.iso_week, dim_date.week_start ... (22 columns) |
| Price | fact_sales_line.unit_price, fact_sales_line.line_revenue, fact_sales_line.is_exact_duplicate_within_source, dim_product.median_unit_price, agg_daily_sales.gross_sales_revenue, agg_daily_sales.cancellation_revenue, agg_daily_sales.net_revenue, agg_weekly_sku_demand.gross_sales_revenue, agg_weekly_sku_demand.cancellation_revenue, agg_customer_rfm_base.monetary_gross, agg_customer_rfm_base.monetary_net (11 columns) |
| Customer ID | fact_sales_line.customer_key, fact_sales_line.customer_identified, fact_sales_line.is_exact_duplicate_within_source, dim_customer.customer_key, agg_customer_rfm_base.customer_key (5 columns) |
| Country | fact_sales_line.country, fact_sales_line.is_exact_duplicate_within_source, dim_customer.country_primary, dim_customer.n_countries, agg_daily_sales.country (5 columns) |

## Keys and grain

| Table | Grain | Primary key | Foreign keys |
|---|---|---|---|
| fact_sales_line | One retained invoice line (sale or cancellation) | line_id | stock_code -> dim_product.stock_code; customer_key -> dim_customer.customer_key (nullable); invoice_date -> dim_date.date |
| dim_product | One merchandise stock code | stock_code | - |
| dim_customer | One pseudonymised customer | customer_key | - |
| dim_date | One calendar day (observed window) | date | - |
| agg_daily_sales | One calendar day x country | invoice_date, country | invoice_date -> dim_date.date |
| agg_weekly_sku_demand | One ISO week (Monday start) x stock code; sparse (weeks with no transactions are absent) | week_start, stock_code | stock_code -> dim_product.stock_code |
| agg_customer_rfm_base | One pseudonymised customer | customer_key | customer_key -> dim_customer.customer_key |

## Record disposition (what happens to each raw row)

Every raw row receives exactly one of `retained`, `quarantined` or `excluded` with a reason code (see `cleaning.REASON_ORDER`). Raw rows = retained + quarantined + excluded is a critical reconciliation check on every run.
