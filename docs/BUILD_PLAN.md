# Step-by-step build plan

> Original target design. For the current runnable release, verification results and deliberate simplifications, read [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

Complete the working system before recording the walkthrough. The phases are ordered by dependency, not by promised calendar dates. Keep all evidence under a batch/rehearsal ID. Detailed acceptance cases are in [TEST_PLAN.md](TEST_PLAN.md).

## Phase 1 — Freeze the environment and prove connectivity

1. Select AWS region, source hosting, Snowflake account, local Airflow host and Windows/Power BI recording machine.
2. Record compatible tested versions: Python, Java, PostgreSQL, MongoDB, Airflow core/providers, Glue runtime/Spark, Mongo connector, Snowflake client and Power BI Desktop.
3. Implement infrastructure declarations and an environment example containing placeholders only.
4. Create private source connectivity, S3 prefixes, secrets, logs and minimum service roles; set development spend alerts and resource expiry tags.
5. Start the synthetic databases, create schema and seed deterministic baseline records.
6. Run a tiny Glue JDBC read into S3 and a tiny MongoDB read. Confirm actual cloud reachability before expanding the pipeline.

**Done when:** both cloud extraction proofs work, dependency versions are recorded and a cleanup procedure exists. **Capture:** source rows, nested document, network diagram and first S3 objects. Covers DE-01–03, DE-17.

## Phase 2 — Extraction and batch contracts

1. Implement the pipeline lease, batch initialization and control-table watermark reads.
2. Define the manifest schema and immutable per-attempt paths.
3. Build all core extractors with bounds, overlap, explicit types and soft deletions.
4. Add customer/product lookup snapshots and affected-order expansion for correct incremental joins.
5. Write manifest completion only after all selected objects are durable.
6. Run baseline, one changed record, empty window and retry cases.

**Done when:** raw evidence reproduces the selected batch without ambiguous attempts. **Capture:** extraction predicate, source change and manifest. Covers DE-04–05.

## Phase 3 — Validation and PySpark

1. Implement Lambda checks for expected datasets, completion flags, keys, bounds and object metadata.
2. Implement explicit Spark schemas, count reconciliation and row quality rules.
3. Flatten customer profile fields, deduplicate and validate lookup uniqueness.
4. Join changed/affected orders and lines to complete lookup snapshots.
5. Write invalid records with reason codes; fail publication for critical schema/key/count problems.
6. Write typed curated Parquet and a manifest; verify fixture sales arithmetic.

**Done when:** missing files stop processing, zero-row completed datasets pass, bad rows quarantine, and joins preserve the line grain. **Capture:** bad input → quality result → curated rows. Covers DE-06–08.

## Phase 4 — Warehouse and publication

1. Create Snowflake roles, warehouse, schemas, stages, formats, tables, control ledger and analytical views.
2. Configure the AWS trust policy and Snowflake storage integration; test scoped access to curated objects.
3. Implement bounded SQL submission/polling and persist query IDs; test reconnection after a submit timeout.
4. COPY only selected batch files into persistent batch/attempt-scoped staging. Record loaded rows and reconcile counts.
5. Implement customer history closure/insertion and fact updates in a DML publication transaction.
6. Commit ledger/watermarks inside the same transaction; return existing success when that batch is already published.
7. Verify baseline totals, updated customer history and replay invariance.

**Done when:** replay preserves metrics and injected publication failure changes neither targets nor watermarks. **Capture:** external stage, COPY result, SQL history and history table. Covers DE-09–12.

## Phase 5 — End-to-end orchestration and operations

1. Build Step Functions Standard workflow with parallel extraction, Glue synchronous waits, validation/quality branches and load/publish polling.
2. Classify errors, bound retries/timeouts and preserve original diagnostic IDs.
3. Build the Airflow start/wait path and map AWS failed/timed-out/aborted states to DAG failure.
4. Add correlated logs, notification routing, lease heartbeats and recovery procedures.
5. Rehearse missing manifest, duplicate start, in-flight SQL timeout and notification failure.

**Done when:** one manual and one scheduled-path test finish with correct terminal states. **Capture:** Airflow graph, AWS graph, deliberately failed state and recovery. Covers DE-13–15, DE-17.

## Phase 6 — Power BI and reproducible release

1. Connect a read-only BI role to published marts using Power BI Import for this demo.
2. Build cards for sales, paid orders, AOV and payment attempt success; add daily trend, category and customer tier views.
3. Show the last published batch timestamp and metric definitions in the report.
4. Refresh only after publication. Use a manual Desktop refresh in the base tutorial; automate Service refresh only as the verified extension.
5. Rebuild from the setup documentation in a fresh development environment and run the complete acceptance suite.
6. Prepare the repository release, sanitised sample outputs, architecture and cleanup instructions. A remote publication step comes after local verification.

**Done when:** dashboard and SQL totals agree and the documented setup reproduces them. **Capture:** dashboard refresh and reconciled query results. Covers DE-16 and VID-02.

## Phase 7 — Record, edit and package

Follow [RECORDING_CHECKLIST.md](../tutorial/RECORDING.md). Record successful and failure demonstrations first; record the opening dashboard proof after the project works. Use the frame plan to assemble the story, replace estimated timing with measured timing, and finish the publishing checklist.

**Done when:** a reviewed 25–35 minute export, measured chapters, captions, selected thumbnail and verified repository links are ready. Covers VID-01–05.
