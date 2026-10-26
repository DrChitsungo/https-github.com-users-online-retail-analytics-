"""Published output catalog: grain, keys, consumers and refresh. Single source of truth for docs and manifests."""

CATALOG = {
    "fact_sales_line": {
        "grain": "One retained invoice line (sale or cancellation)", "primary_key": ["line_id"],
        "foreign_keys": {"stock_code": "dim_product.stock_code", "customer_key": "dim_customer.customer_key (nullable)", "invoice_date": "dim_date.date"},
        "consumers": ["Data engineering / analytics modelling layer", "Power BI semantic model (detail drill-through, restricted)"],
        "sensitivity": "Pseudonymous (customer_key) - restricted access",
    },
    "dim_product": {
        "grain": "One merchandise stock code", "primary_key": ["stock_code"], "foreign_keys": {},
        "consumers": ["Inventory and Procurement", "E-commerce and Operations (merchandising)", "Forecasting models"],
        "sensitivity": "Business data; free text scrubbed of personal-name patterns",
    },
    "dim_customer": {
        "grain": "One pseudonymised customer", "primary_key": ["customer_key"], "foreign_keys": {},
        "consumers": ["Marketing (RFM/segmentation)", "Churn and lifetime-value models"],
        "sensitivity": "Pseudonymous - restricted access",
    },
    "dim_date": {
        "grain": "One calendar day (observed window)", "primary_key": ["date"], "foreign_keys": {},
        "consumers": ["All reporting and forecasting consumers"], "sensitivity": "None",
    },
    "agg_daily_sales": {
        "grain": "One calendar day x country", "primary_key": ["invoice_date", "country"], "foreign_keys": {"invoice_date": "dim_date.date"},
        "consumers": ["Business leaders and Finance (executive dashboard)", "E-commerce and Operations (sales dashboard)", "Exception alerts"],
        "sensitivity": "Aggregated; small-country cells need suppression rules before wide sharing",
    },
    "agg_weekly_sku_demand": {
        "grain": "One ISO week (Monday start) x stock code; sparse (weeks with no transactions are absent)", "primary_key": ["week_start", "stock_code"],
        "foreign_keys": {"stock_code": "dim_product.stock_code"},
        "consumers": ["Inventory and Procurement (weekly SKU forecasts, reorder support)", "Demand forecasting models"],
        "sensitivity": "Aggregated business data",
    },
    "agg_customer_rfm_base": {
        "grain": "One pseudonymised customer", "primary_key": ["customer_key"], "foreign_keys": {"customer_key": "dim_customer.customer_key"},
        "consumers": ["Marketing (RFM segments, campaign design)", "Churn and lifetime-value models"],
        "sensitivity": "Pseudonymous - restricted access",
    },
}
