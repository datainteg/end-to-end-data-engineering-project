# Build the Power BI report

No `.pbix` is supplied because no Snowflake-connected Power BI session has been executed. This guide defines the report to build after cloud publication succeeds.

1. In Power BI Desktop, choose **Get data → Snowflake**. Supply your account server and warehouse, then authenticate with the read-only BI role approved for that account.
2. Use Import for this small demonstration. Select `MART_SALES`, `FACT_ORDERS`, `FACT_PAYMENTS`, `DIM_DATE`, and optionally `MART_KPIS` for SQL reconciliation.
3. Set `DIM_DATE.DATE_KEY` to Date. Create one-to-many, single-direction relationships from it to `MART_SALES.DATE_KEY` and `FACT_ORDERS.DATE_KEY`. Do not create an ambiguous direct relationship between sales lines and payment attempts. Payment success below is all loaded attempts; label it separately from date-filtered sales.
4. Add the measures in `measures.dax`. Store them in a dedicated Measures table or one of the imported tables.
5. Create cards for demo net sales (₹), paid orders, AOV (₹), and all-attempt success (%). Create monthly sales using Date, plus a bar chart by `TIER_OBSERVED_AT_FIRST_PUBLICATION`. Label the whole report **Synthetic data • batch demo**.
6. Refresh after a published batch, run `sql/snowflake/validate.sql`, and compare all four cards. Baseline: ₹1,200, 2, ₹600, 50%.
7. Replay publication and refresh: values must stay unchanged. Process a customer tier change: existing sales keep their original observed tier.
8. Import `BATCH_LEDGER` to show last published upper bound if desired. A refresh timestamp alone is not proof of source freshness.

Net sales excludes cancelled/deleted orders and deleted lines via the warehouse mart. Paid orders includes paid nondeleted order headers, even if all their lines are later deleted. Payment success is successful nondeleted attempts divided by all nondeleted attempts. Do not calculate success as successful orders / payment attempts.

Do not join payments directly to order lines; this multiplies sales when an order has multiple attempts. Do not call these fixture metrics accounting revenue or predictive lifetime value. Manual Desktop refresh is the supported tutorial procedure; no Power BI Service automation is claimed.
