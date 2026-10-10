# Architecture: current pipeline and advanced design

The project separates a verified local reference, supplied cloud integration code, and a proposed production design. The [implementation status](IMPLEMENTATION_STATUS.md) is the authority for what has actually run. These diagrams make the architecture easier to explain; they do not deploy new services.

**Start here:** [editable draw.io file](diagrams/ecommerce-architecture.drawio) · [diagram gallery and editing guide](diagrams/README.md) · [project interview questions](INTERVIEW_QUESTIONS.md).

## Current cloud workflow

![Current supplied cloud workflow](diagrams/cloud-workflow.svg)

Read the main path across the top processing row and back across the lower row. The supplied implementation uses frozen full snapshots, not incremental extraction. One Glue extraction job reads PostgreSQL through its JDBC connector and MongoDB through a named connection, sequentially. These are not a shared database snapshot.

| Boundary | Responsibility | Code / evidence |
| --- | --- | --- |
| Sources → raw | Preserve five complete datasets under a fresh immutable attempt | [extract_sources.py](../jobs/extract_sources.py) |
| Raw → validated | Verify expected sources, selected paths, bounds, counts and checksums | [manifest validator](../lambdas/validate_manifest/handler.py) |
| Validated → curated | Shared capped quality checks, explicit Spark schemas, grain-safe joins, decimal Parquet | [transform_curated.py](../jobs/transform_curated.py) |
| Curated → staging | Load only selected files and reconcile counts/keys | [Snowflake runner](../scripts/publish_snowflake.py) |
| Staging → published | Commit dimensions, facts, ledger and watermarks together | [publish.sql](../sql/snowflake/publish.sql) |
| Published → report | Read published marts and compare dashboard definitions with SQL | [Power BI guide](../powerbi/README.md) |

Raw validation and transformation are deliberately bounded for the teaching fixture. The cloud path caps each source at 10,000 records, uses driver-side validation and blocks publication if quarantine is nonempty. See [data contracts](DATA_CONTRACTS.md) for grains and definitions.

### Data and control are separate

Airflow starts a Standard Step Functions workflow and waits for its terminal state. The supplied DAG is manually triggered. Step Functions coordinates the three Glue jobs using synchronous job tasks; it passes IDs and configuration, not the source rows. Lambda performs bounded validation/control work. Snowflake executes the warehouse SQL.

A DynamoDB mutex serializes workflow publication. Its conditional acquire/release calls are made by the lock Lambda. The mutex does not expire: failure after acquisition retains ownership until an operator reconciles old jobs, queries and the batch ledger. Airflow's single active run alone cannot protect starts made outside that DAG.

The supplied Snowflake bridge is a synchronous Glue driver job. It does not implement the advanced submit/poll Lambda bridge shown on the proposal page. Do not confuse “Glue job runs synchronously under Step Functions” with “every SQL execution has durable asynchronous recovery.”

### The publication boundary

1. Load session-specific staging tables and validate selected row counts/keys.
2. Check mutex ownership and whether the batch already committed.
3. Apply customer history, product/date changes and separate fact updates.
4. Update committed publication watermarks and insert the ledger row in the same database transaction.
5. Commit, then release the workflow lock after successful processing.

If SQL fails before commit, business changes and watermarks roll back. If the client loses the response, reconcile the ledger and query state first. S3 audit files, SNS notifications and Power BI refresh are outside that database transaction. A notification error is not a reason to republish facts. This is not a distributed exactly-once guarantee.

### Source network and security boundaries

Glue workers accessing private databases require the correct VPC/subnet routing, DNS and security groups. Configure source TLS and access to S3, Secrets Manager and required service endpoints. The publisher also needs Snowflake connectivity. Step Functions itself is a managed orchestration service, not a database worker inside the source subnet.

Use scoped service roles, encrypted storage and a role-based Snowflake S3 storage integration. Keep source secrets out of workflow input, logs and Git. The supplied CloudFormation foundation creates storage, a lock table and an SNS topic; it does not configure every network/IAM/service resource. Follow [CLOUD_SETUP.md](CLOUD_SETUP.md) for account-specific setup and costs.

### Actual object layout in this release

```text
raw/batch_id=<id>/attempt_id=<id>/
  dataset=orders/part-00000.jsonl
  dataset=order_items/part-00000.jsonl
  dataset=payments/part-00000.jsonl
  dataset=products/part-00000.jsonl
  dataset=customers/part-00000.jsonl
  manifest.json
curated/batch_id=<id>/attempt_id=<id>/
  <dataset>/part-*.parquet
  manifest.json
rejected/batch_id=<id>/attempt_id=<id>/rows.json
audit/batch_id=<id>/attempt_id=<id>/quality.json
scripts/<release>/...
```

Completed zero-row raw datasets may have no data file. The cloud transformer also writes a sales dataset. Snowflake staging is session-specific database storage; a separate S3 staging layer is not implemented. The local reference uses the same raw attempt layout, but stores published data in SQLite and quality evidence in its local audit directory.

## Warehouse model

![Dimensions and fact grains](diagrams/warehouse-model.svg)

`FACT_ORDERS` contains one order, `FACT_SALES` one order line, and `FACT_PAYMENTS` one payment attempt. Keep sales and payments separate: joining multiple attempts directly to a line multiplies sales. Dates attach to order headers; the sales mart obtains dates through those headers.

`DIM_CUSTOMER` preserves observed versions. C001 Silver closes when the Gold observation starts; existing facts retain their original customer surrogate key. The label is “tier observed at first publication,” not “tier at original order time.” Product attributes are Type 1. Soft deletions propagate as explicit state; hard-delete capture is a separate extension.

## Advanced upgrade plan

![Proposed advanced production design](diagrams/advanced-roadmap.svg)

This is an implementation roadmap, not a claim of completed work. Complete the cloud connectivity and publication proofs before adding more services.

| Upgrade | Why it matters | Mechanism to build | Evidence required |
| --- | --- | --- | --- |
| Incremental extraction | Avoid rescanning all source rows | W/U bounds, overlap, affected-order expansion and complete lookup state | Baseline, late change, unchanged lookup, empty delta and replay agree |
| Distributed quality | Remove the teaching driver's memory ceiling | Spark-native rules, dedupe and reconciliation | Representative volume/skew test; counts and amounts preserved |
| File/partition strategy | Reduce small-file and unnecessary scan overhead | Measured Parquet sizing, partition selection, controlled compaction | Query/runtime/cost comparison with recorded data volumes |
| Async SQL bridge | Recover long operations across client timeouts | Persist handles, submit/poll, reconcile/cancel before resubmission | Lost-response, reconnect, cancellation and committed-replay tests |
| Safe ownership handoff | Automate recovery without overlapping publishers | Proven fencing or strict cancellation/reconciliation before transfer | Old writer cannot commit after ownership transfers; forced pause/resume test |
| Schema governance | Make upstream changes explicit | Versioned contracts, compatibility rules and migration gates | Missing required fields fail; allowed optional fields are handled predictably |
| Controlled backfills | Correct old business periods intentionally | Audited restatement path with defined history attribution | Repeated backfill stable; normal watermarks remain coherent |
| Operational visibility | Detect stale or incorrect data, not just failed jobs | Batch/query correlation, freshness/quality alerts, notification-only retries | Simulated stale batch/lock and follow-up failure alert correctly |
| Optional CDC | Capture deletes or intermediate changes when required | Source-specific logs, ordering, offsets and replay retention | Delete, out-of-order, restart and retention-boundary tests |

A DynamoDB TTL is not a fencing mechanism. A time-expired lease does not prove the old Snowflake query stopped. Similarly, a source timestamp overlap is not a complete source-change history. State these trade-offs explicitly in interviews.

## Explain it in five steps

1. Define the business result and the grain of each source/fact.
2. Follow one order through the raw manifest, quality checks and curated output.
3. Show the single warehouse commit boundary and stable customer attribution.
4. Break a file or inject a failure; explain why the watermark does not advance.
5. Identify a measured bottleneck before choosing one proposed improvement.

Use [INTERVIEW_QUESTIONS.md](INTERVIEW_QUESTIONS.md) for short answers and scenario practice. Use the [local diagram](diagrams/local-reference.svg) when showing what can be reproduced without cloud accounts.

## Primary technical references

- [AWS Glue integration with Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/connect-glue.html)
- [Glue JDBC VPC connectivity](https://docs.aws.amazon.com/glue/latest/dg/connection-JDBC-VPC.html)
- [Airflow Step Functions operators and sensors](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/operators/step_functions.html)
- [Snowflake transactions](https://docs.snowflake.com/en/sql-reference/transactions)
- [Snowflake S3 storage integrations](https://docs.snowflake.com/en/user-guide/data-load-s3-config-storage-integration)

These references support the service/API choices. They are not execution evidence for the supplied code.
