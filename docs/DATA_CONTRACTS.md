# Data contracts and metric definitions

Proposed schema v1. All records are synthetic. IDs are stable strings, times are UTC, money is DECIMAL(18,2), currency is INR for the demo. Required fields are non-null unless stated. Normalize MongoDB identifiers to strings, preserve nested raw JSON, and use explicit Spark schemas.

## Source grains

| Dataset | Grain / primary key | Required business fields |
| --- | --- | --- |
| PostgreSQL orders | One order / order_id | customer_id, ordered_at, status, currency, updated_at, is_deleted |
| PostgreSQL order_items | One line / order_id + line_id | product_id, quantity, unit_price, discount_amount, updated_at, is_deleted |
| PostgreSQL payments | One attempt / payment_id | order_id, amount, status, attempted_at, updated_at, is_deleted |
| PostgreSQL products | One product / product_id | product_name, category, updated_at, is_deleted |
| MongoDB customers | One customer / customer_id | profile.city (nullable), profile.loyalty_tier, updated_at, is_deleted |
| MongoDB reviews (extension) | One review / review_id | customer_id, product_id, rating, created_at, updated_at |
| MongoDB activity (extension) | One event / event_id | customer_id, event_type, event_at, updated_at |

Every writer must update `updated_at` on inserts, edits and soft deletions. Index extraction fields. Do not assume a MongoDB ObjectId tracks edits. Mutable timestamp extraction is best effort without stronger source guarantees; backdated edits and intermediate changes can be missed.

## Incremental and replay contract

1. Capture immutable upper bound U at batch initialization and read per-dataset committed lower watermark W. UTC bounds and schema version go into the manifest.
2. Use a documented overlap, initially five minutes for this demonstration: `updated_at >= W - overlap AND updated_at < U`. Initial load uses an explicit earliest bound. Overlap is an assumption to validate, not a universal correctness guarantee.
3. Read the same logical window on retry but write a new attempt prefix. Select only one completed attempt per dataset. Because live source records can change, prefer replay from preserved raw files when reproducing a batch exactly.
4. Collapse overlap/repeated keys to one latest record by key and `updated_at`; exact duplicates collapse deterministically. Conflicting payloads at the same key/time fail instead of choosing arbitrarily.
5. Persist all new W=U values only when the warehouse publication transaction succeeds. Valid empty datasets advance their watermark with the successful batch.
6. Soft deletions propagate as explicit state. Hard deletes require tombstones, CDC or periodic full reconciliation and are outside the basic timestamp extractor.

PostgreSQL and MongoDB extractions are not a shared distributed snapshot. Use a controlled fixture for the demonstration; document eventual reconciliation for live source skew. Bounded overlap cannot recover unbounded late commits or preserve every intermediate version.

## Incremental joins

Never join only today's changed orders with only today's changed customers. The missing unchanged side would drop valid sales. For the small tutorial fixture, extract a complete customer and product lookup snapshot at U alongside their deltas; join changed order lines to these snapshots. Record snapshot counts separately from delta counts. For line/header consistency, collect affected order IDs from changed orders and changed lines, then re-read all lines and headers for those orders. The batch manifest records this expansion. A scalable extension maintains durable source-state tables instead of rereading full dimensions.

Do not join reviews or multiple payment attempts directly into sales lines. Aggregate them to the intended grain first, or keep separate facts. Distinct counts cannot repair already-multiplied revenue sums.

## Warehouse contracts

| Model | Grain and behavior |
| --- | --- |
| DIM_CUSTOMER | One observed customer version; surrogate customer_sk, customer_id, tracked attributes/hash, valid_from, valid_to, is_current, is_deleted |
| DIM_PRODUCT | One current product; Type 1 update for category/name; soft-delete flag |
| DIM_DATE | One UTC calendar date, date_key |
| FACT_ORDERS | One order; customer_sk, date_key, status, deletion state |
| FACT_PAYMENTS | One payment attempt; order_id, status, decimal amount; independent from sales |
| FACT_SALES | One order line; order_id + line_id, customer_sk, product key, quantity, line revenue, status/deletion state |

SCD2 uses observed batch-effective history: a changed tracked-attribute hash closes the current version at batch U and inserts the next version starting at U. Use half-open validity intervals. First observed profiles begin at their initial observation; this is not proof of their true historical source state. Facts retain the customer version assigned at their first publication; later corrections retain that key unless an explicit restatement rule is added. Label customer segmentation as “tier observed at first publication,” not “tier at order time.” Late facts get the version known at ingestion. Historical reconstruction requires source history beyond this tutorial.

Publish SCD2 changes, fact updates, audit and watermarks atomically. Dedupe source rows first; replay checks the batch ledger. Test one current version per customer and no overlapping intervals. A basic matched-row MERGE update is Type 1, not a complete SCD2 algorithm; see [Snowflake MERGE semantics](https://docs.snowflake.com/en/sql-reference/sql/merge).

## Manifest contract

Manifest fields: `schema_version`, `pipeline_id`, `batch_id`, `attempt_id`, `window_upper_utc`, `created_at`, and a `datasets` array. Each dataset includes source/name, extraction mode (delta/snapshot/affected-orders), lower bound, upper bound, schema fingerprint, status, record count and an explicit file list with key, bytes and available checksum. Do not treat all S3 ETags as content MD5 hashes.

Every expected dataset must be present with status COMPLETE. Zero rows plus an empty file list is valid if explicitly completed. Nonzero rows without files fail. Reject references outside the batch/attempt prefixes. Lambda validates structure, completeness, object metadata and bounded samples; Spark scans actual data to reconcile declared counts and enforce row-level types/quality.

## Business calculations and fixture

Line revenue = quantity × unit_price − discount_amount, where discount_amount is the total line discount. Include paid, nondeleted orders/lines; exclude cancelled orders. Taxes, shipping, returns and currency conversion are outside this fixture. Call this “demo net sales,” not an accounting-complete revenue measure.

| Fixture | Lines | Payments | Expected contribution |
| --- | --- | --- | --- |
| O100, C001, paid | 2 × ₹500 − ₹100 | P100 SUCCESS ₹900 | ₹900 |
| O101, C002, paid | 1 × ₹300 − ₹0 | P101 FAILED ₹300; P102 SUCCESS ₹300 | ₹300 |
| O102, C001, cancelled | 1 × ₹200 − ₹0 | P103 FAILED ₹200 | ₹0 |

Expected demo net sales ₹1,200; paid orders 2; AOV ₹600; successful-payment-attempt rate 2/4 = 50%. Monthly revenue aggregates the same measure. Observed customer spend is the sum over available history; do not label a partial fixture as predictive lifetime value. Replay must leave these values unchanged. A separate invalid line (quantity −1) is quarantined and is excluded from the baseline fixture above.

Quality accounting is per dataset/grain: input = accepted + quarantined + superseded duplicates, with distinct stages recorded to avoid double-counting. Reconcile joins separately and ensure uniqueness on each dimension join key.
