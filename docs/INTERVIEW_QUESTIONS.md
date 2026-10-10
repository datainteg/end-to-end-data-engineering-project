[← Project home](../README.md) · [All docs](README.md) · [Code tour](CODE_TOUR.md) · [Hands-on tutorial](../tutorial/WALKTHROUGH.md)

# Project interview questions and simple answers

Use these as practice answers, not a script to memorize. Start with the short answer, then open the linked code or test when asked for evidence. **The local reference and source seed are verified; the AWS/Snowflake code is an unverified integration lab.** The advanced diagram is a proposal, not deployed work.

## Choose a practice topic

| Foundation | Implementation | Discussion |
| --- | --- | --- |
| [1–6 · Project story](#explain-the-project-first) | [17–25 · Quality and metrics](#quality-and-business-calculations) | [35–40 · Operations](#orchestration-security-and-operations) |
| [7–16 · Sources and loading](#sources-storage-and-extraction) | [26–34 · History and replay](#warehouse-history-and-safe-replay) | [41–45 · Advanced trade-offs](#advanced-follow-ups-proposals-not-completed-features) |

[12 scenario questions](#scenario-questions-say-the-action-and-the-evidence) · [Ten-minute practice plan](#ten-minute-interview-practice)

<details>
<summary><strong>How to give a strong project answer</strong></summary>

Use **decision → reason → evidence → limit**. Example: “I keep payment attempts separate from sales lines because retries would multiply revenue. The fixture has two attempts for O101 but one ₹300 sales line. The local tests verify the totals; cloud execution is still pending.”

</details>

## Explain the project first

### 1. Tell me about this project in one minute.

“I built a small e-commerce batch pipeline reference that turns orders, order lines, payments and customer profiles into trusted sales metrics. The local version archives inputs, validates them, tracks customer history and publishes data in one database transaction. I tested replay, missing files, rollback and duplicate handling. I also supplied a cloud integration path using Glue, S3, Lambda and Snowflake, with Airflow and Step Functions orchestration; that path still needs account-level validation.”

**Show:** [architecture diagrams](diagrams/README.md), [test evidence](VALIDATION.md).

### 2. What business problem does it solve?

It brings separate sales and customer data together to answer four questions: net sales, paid orders, average order value and payment-attempt success. It also prevents a retry or a bad join from quietly changing those numbers.

### 3. What did you personally implement and test?

The repository contains the fixture, immutable local raw attempts, validation, quality rules, SQLite publication, SCD2 history and failure tests. PostgreSQL/MongoDB seeding and reseeding were also checked. Cloud code was written and syntax checked, but I would not describe that as a successful AWS deployment.

### 4. What is the end-to-end flow?

Local: fixture → raw JSONL and manifest → validation and cleaning → SQLite transaction → sales metrics. Cloud code: PostgreSQL/MongoDB → Glue → raw S3 → Lambda validation → PySpark → curated S3 → Snowflake → Power BI guide. [Open the diagrams](diagrams/README.md).

### 5. Why batch instead of streaming?

The demonstration needs consistent periodic reporting, not sub-second decisions. Batch makes the data boundary and replay easier to explain. I would choose streaming only after defining a latency requirement that justifies the extra operational complexity.

### 6. Why keep a local version?

It makes correctness tests fast, reproducible and accessible without paid services. It proves the local business rules, not AWS networking, Spark behavior or Snowflake transaction behavior. Those require separate integration tests.

## Sources, storage and extraction

### 7. Why PostgreSQL and MongoDB?

Orders and payments fit relational tables with defined keys. Customer profiles demonstrate nested document data. The point is to preserve the meaning of both sources while bringing them into a common analytical model; neither database is mandatory for all businesses.

### 8. Is a Python PostgreSQL connection the same as JDBC?

No. The seed tool uses psycopg. The cloud extractor uses Glue's PostgreSQL connector, which is the JDBC extraction path. I would show actual Glue job logs before claiming that cloud connection was verified. [Extractor](../jobs/extract_sources.py).

### 9. What is the difference between a batch ID and an attempt ID?

A batch ID identifies one logical publication. An attempt ID identifies one extraction attempt for it. A failed extraction gets a fresh attempt so it does not overwrite the old raw evidence. A committed batch must not be reused for different content.

### 10. What is a manifest?

It is the receipt for the batch: datasets, selected files, counts, checksums, schema version and time bounds. Downstream processing uses that explicit file list instead of assuming every file in a folder belongs to the current run. [Validation contract](../pipeline/contracts.py).

### 11. Why keep raw data immutable?

It provides evidence of what was actually processed and allows replay without rereading changed sources. Fixes should create new attempts, not rewrite a published attempt. This implementation prevents ordinary overwrite; it does not implement S3 Object Lock or a regulatory retention guarantee.

### 12. Are raw, staging and curated the same thing?

No. Raw preserves extracted records. Curated contains typed, validated Parquet for loading. Snowflake staging is a temporary loading area before business publication. The current cloud code does not write a separate S3 staging zone; the original target design proposed one for control manifests.

### 13. Does this project implement incremental extraction?

Not in this release. It uses small, frozen full snapshots, with a 10,000-record cap per cloud dataset. Its watermarks record successful publication boundaries. The incremental window and affected-order design is a proposed extension, not currently executed code.

### 14. How would you add incremental loading?

Read committed watermark W, choose upper bound U, and extract changes in a bounded window with a documented overlap. Rebuild complete affected orders and keep complete customer/product lookup state. Deduplicate the overlap and advance W only after publication commits. Timestamp overlap still misses some backdated or intermediate changes; CDC is a separate design choice.

### 15. Why can't you join only changed orders to changed customers?

An order may change while its customer does not. Joining only the two deltas can drop that order. Use complete lookup snapshots or durable source-state tables, then join affected orders to that complete lookup state.

### 16. How do you handle deleted records?

The source carries an `is_deleted` flag, and the warehouse preserves that state. Deleted orders or lines no longer contribute to sales. Deleting a customer/product dimension does not erase earlier sales. Hard deletes are not detected by the current snapshot/upsert implementation; they require tombstones, CDC or explicit reconciliation.

## Quality and business calculations

### 17. What does “grain” mean here?

It means what one row represents. `FACT_ORDERS` is one order, `FACT_SALES` is one order line, and `FACT_PAYMENTS` is one payment attempt. Design the keys and joins around those meanings. [Warehouse model](diagrams/warehouse-model.svg).

### 18. How can a join make revenue wrong?

Order O101 has one ₹300 sales line and two payment attempts. Joining the line directly to both attempts gives two rows and an incorrect ₹600 sum. Keep separate facts or aggregate to the required grain first. `COUNT(DISTINCT order_id)` does not fix a multiplied revenue sum.

### 19. How do you calculate the four KPIs?

| Metric | Definition | Baseline |
| --- | --- | --- |
| Demo net sales | Sum of quantity × unit price − total line discount for paid, nondeleted orders/lines | ₹900 + ₹300 = ₹1,200 |
| Paid orders | Count of paid, nondeleted order headers | 2 |
| AOV | Demo net sales / paid orders | ₹600 |
| Payment-attempt success | Successful nondeleted attempts / all nondeleted attempts | 2/4 = 50% |

Paid orders can still count a paid header whose lines are all later deleted. That is the documented metric definition, not an accidental difference between SQL and Power BI.

### 20. Why avoid floating point for money?

Some decimal fractions cannot be represented exactly as binary floating-point values. The local warehouse stores integer paise; cloud output uses decimal columns. For example, ₹900 is stored locally as 90000 paise. The fixture has one currency, INR; no currency conversion is implemented.

### 21. What does validation check, and what does cleaning check?

Manifest validation checks completeness, selected paths, bytes and SHA256 integrity. Cleaning checks required fields, keys, types, duplicate conflicts, references and business rules. A file can have the right checksum and still contain a negative quantity.

### 22. How are duplicates handled?

Exact duplicate records collapse. A later `updated_at` version supersedes an earlier version of the same key. Conflicting records at the same key and timestamp fail, because choosing one arbitrarily would hide ambiguity. [Cleaning code](../pipeline/local.py).

### 23. What is quarantine?

It is a separate record of rejected rows and their reasons, such as `NONPOSITIVE_QUANTITY`. Locally, new invalid line/payment rows can be quarantined while valid rows publish; invalid corrections to existing facts block publication. The cloud path writes rejection evidence and blocks publication whenever quarantine is nonempty.

### 24. How do you prove rows were not lost?

Check input = accepted + quarantined + superseded duplicates for each dataset. Then check join counts and key uniqueness separately, and reconcile business totals against the fixture. Counting rows alone is insufficient: the same number of rows can still contain wrong amounts.

### 25. Can a zero-row dataset be valid?

Yes, if the manifest explicitly says extraction completed with zero rows and no files. A missing dataset or a nonzero count with no files fails. An empty snapshot is not interpreted as permission to delete all existing warehouse rows.

## Warehouse, history and safe replay

### 26. What is a fact table versus a dimension table?

Facts hold events or measurements, such as sales lines and payment attempts. Dimensions hold descriptive context, such as product category and observed customer tier. `DIM_DATE` is referenced by orders; a sales line reaches its date through its order in the supplied model.

### 27. What is SCD Type 2?

It keeps versions of selected dimension attributes. When C001 changes Silver → Gold, close the old version at batch U and create a new current version beginning at U. An unchanged profile does not create another version. [Local implementation](../pipeline/local.py), [Snowflake publication SQL](../sql/snowflake/publish.sql).

### 28. Why use a surrogate customer key?

A natural customer ID identifies the customer across time; a surrogate key identifies one stored version. Facts retain the version assigned at first publication. That is why a later tier change does not automatically reclassify all earlier sales.

### 29. Does this preserve the customer's true tier at order time?

No. It preserves the profile versions observed by the batch process. The correct label is “tier observed at first publication.” Exact historical reconstruction requires source change history that this fixture does not provide.

### 30. What does idempotency mean in your project?

Repeating publication of an already committed selected batch does not add facts or customer versions. The ledger detects completion; the local path checks normalized accepted content and bounds, and the cloud runner checks the selected curated manifest hash. Cloud replay uses the original manifest under the mutex, not a rerun of extraction into the same immutable path.

### 31. What changes are in the publication transaction?

Dimensions, facts, quality control rows locally, the successful batch ledger and publication watermarks commit together. Snowflake publication also commits its business tables and ledger/watermarks together; S3 audit objects remain outside that database transaction. Bootstrap DDL is separate. An exception before commit rolls the database changes back.

### 32. What if the database commits but the client times out?

First reconcile the batch ledger and the running query, rather than assuming failure. If committed, repair only any remaining follow-up work. The local replay test demonstrates the ledger behavior; this repository does not contain a real cloud lost-response integration test.

### 33. Is this exactly-once processing?

I would describe it as replay-safe database publication under a serialized-writer contract, not distributed exactly-once delivery across AWS, Snowflake and Power BI. Raw extraction, SQL commit and notification delivery are separate boundaries.

### 34. Why not update the watermark as soon as extraction completes?

A later validation or publication failure would move the boundary past uncommitted data. Keep the old committed watermark until the business transaction succeeds. The rollback tests verify that local target changes and watermarks stay together.

## Orchestration, security and operations

### 35. Why both Airflow and Step Functions?

Airflow provides the trigger/scheduling boundary and waits for the final outcome. Step Functions coordinates AWS job execution. This is a teaching choice, not a requirement that every pipeline needs two orchestrators. The supplied DAG is manually triggered; no automatic schedule is enabled.

### 36. Why isn't `max_active_runs=1` enough?

It only limits starts through that Airflow DAG. A manual workflow start could bypass it. The cloud design additionally uses a conditional DynamoDB mutex. Locally, `BEGIN IMMEDIATE` serializes database writers. [Mutex handler](../lambdas/pipeline_lock/handler.py).

### 37. Why does a failed cloud workflow keep the lock?

The old Snowflake query might still be running. The current mutex has no automatic expiration: an operator must reconcile jobs, queries and the ledger before release. This is less automatic but avoids an unsafe timer-based takeover. A future renewable lease needs a verified fencing strategy, not just a TTL.

### 38. How would you secure the pipeline?

Use private source connectivity, TLS, encrypted storage, restricted service roles, Secrets Manager and a Snowflake storage integration. Give the BI role read-only access. Those are account setup requirements and supplied design controls; do not claim all were deployed. No production credentials belong in Git or workflow input.

### 39. What would you monitor?

Batch/attempt IDs, terminal state, selected/input/output/rejected counts, committed upper bound, source-to-mart freshness, job runtime and Snowflake query IDs. Alert on failures, stalled locks and unexpected reconciliation results. CloudWatch/SNS setup is proposed or account-specific; operational dashboards have not been verified.

### 40. How would you reduce cost?

Measure first. Right-size jobs and warehouses, auto-suspend Snowflake compute, retain raw data according to a policy, reduce repeated scans, and avoid excessive small files. Incremental extraction may help once correctly implemented. I would not quote a cost saving or SLA without actual measurements.

## Scenario questions: say the action and the evidence

| Interview scenario | Simple response | Evidence to inspect |
| --- | --- | --- |
| A raw file is missing | Stop before publication; preserve the last committed state; recover from a complete selected attempt | Manifest and unchanged ledger/watermarks |
| The same batch runs twice | Reconcile the ledger; committed replay must not add data | Fact counts, customer versions and KPIs |
| A new row has quantity −1 | Record its reason; apply the documented local/cloud rejection policy | Quality counts and rejection file |
| A published line is corrected to invalid money | Block that correction; do not quietly retain stale data and advance the batch | Failed publication, unchanged watermark |
| The customer tier changes | Close/insert observed history; retain old fact attribution | One current customer row, stable fact key |
| A payment fails and then succeeds | Keep both attempts; count the sale once | Separate sales/payment facts; 50% fixture success |
| A query times out | Check query state and committed ledger before rerunning | Query ID and batch ID |
| Someone starts a second workflow | Reject mutex acquisition while the first owner remains | Conditional-write failure and lock owner |
| An alert fails after commit | Retry the alert, not the business transaction | Published ledger and failed notification |
| A source row is hard deleted | Admit the current limitation; propose explicit deletion capture | Source tombstone/CDC or reconciliation design |
| Dashboard total differs from SQL | Check measure definition, filters, relationships, refresh and loaded batch | MART_KPIS versus report cards |
| A customer ID on an existing order changes | Require an explicit restatement policy; current publisher rejects the ownership change | Validation error, preserved original attribution |

## Advanced follow-ups: proposals, not completed features

### 41. What would you change for millions of rows?

Remove driver collection and move quality/deduplication to distributed Spark operations. Choose partitions based on real volume, keep useful file sizes and handle skew. Implement incremental state and affected-order expansion before claiming less scanning. Load-test skew, replay, backfill and failure paths. [Advanced architecture](diagrams/advanced-roadmap.svg).

### 42. When would you choose CDC?

When I need reliable delete capture, lower latency, or intermediate changes unavailable from current-row snapshots. I would design ordering, offsets, retention and replay around source change logs. CDC introduces new failure and operational concerns; adding its logo is not an implementation.

### 43. How would you handle schema evolution?

Version the contract, reject missing required fields, and define which optional additions are compatible. Update source mapping, typed transformations, warehouse schema and tests together. Decide explicitly how to backfill affected history. Do not silently cast every new type to text.

### 44. How would you handle late data and backfills?

Separate normal incremental publication from an explicit, audited backfill/restatement workflow. Track the affected business period and decide whether historical dimension attribution changes. The current publisher rejects backward publication bounds, so an old-period backfill is not supported just by passing an older date.

### 45. What would you improve next?

First prove the supplied cloud path end to end and record exact runtime versions. Then prioritize incremental correctness, distributed quality checks and safe SQL submit/poll recovery. Add contract/schema checks in CI, freshness monitoring and controlled backfills. Choose improvements from measured problems rather than increasing the service count.

## Ten-minute interview practice

1. **One minute:** explain the business goal, verified scope and four baseline metrics.
2. **Two minutes:** walk the cloud diagram, then point out what runs locally today.
3. **Two minutes:** explain line grain, the payment fan-out example and money types.
4. **Two minutes:** show a customer version change and replay in the local code/tests.
5. **Two minutes:** explain missing-file failure, rollback and the lock recovery rule.
6. **One minute:** choose one advanced improvement and say what test would prove it.

Before the interview, run `python3 -m unittest discover -s tests -v` and the local demo. Use [VALIDATION.md](VALIDATION.md) for executed evidence. Never replace measured experience with claims copied from the proposed architecture.
