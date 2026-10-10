# Implemented behavior and remaining integration work

Updated 10 October 2026 (Asia/Kolkata). The original architecture/build plan describes the target, not a verified deployment. This document takes precedence for release status.

| Area | Supplied implementation | Verification |
| --- | --- | --- |
| Deterministic data and metrics | Shared fixture, decimal input, exact integer paise locally | Local tests passed |
| Source databases | Compose, PostgreSQL DDL, idempotent Python seed | Local PostgreSQL/MongoDB seed, reseed and mutation passed; see VALIDATION.md |
| Raw archive | Immutable attempt directories, JSONL, SHA256 manifests | Local missing/corrupt-file and replay tests passed |
| Quality | Schema/key checks, conflict detection, quarantine, count accounting | Local tests passed |
| Warehouse | SQLite SCD2, facts, dates, products, ledger and atomic watermarks | Baseline, replay, rollback, deletion and mutex tests passed |
| Real Glue extraction | PostgreSQL JDBC + MongoDB connection reads | Code supplied; not run in AWS |
| PySpark | Explicit schemas, decimal Parquet, sales join and grain reconciliation | Code supplied; cloud execution not run |
| Lambda | Bounded checksum validation, durable mutex | Code supplied; AWS integration not run |
| Snowflake | Stage/integration SQL, scoped COPY, SCD2 and fact publication transaction | Code supplied; Snowflake execution not run |
| Orchestration | Step Functions ASL generator, Airflow start + terminal sensor | Generated and syntax checked; managed services not run |
| Infrastructure | S3/DynamoDB/SNS CloudFormation foundation | Template supplied; network/IAM/jobs require account configuration |
| Power BI | Model and DAX instructions | Report not built; no fabricated `.pbix` |
| Interview / architecture | 45 Q&A, 12 scenarios, four editable draw.io pages and SVG previews with tool icons | Diagram previews and XML checked; advanced page is proposed design |
| Teaching | Nine narration files, demonstration and recording directions | Text prepared; audio and footage not recorded |

## Deliberate differences from the original plan

1. Full snapshots are the implemented extraction mode. They require a frozen teaching source and include unchanged lookups automatically. Incremental delta windows, overlap and affected-order expansion remain target design work.
2. One Glue extraction job reads both sources sequentially. They are not a distributed snapshot. Stop fixture writers while extracting.
3. Cloud validation/transform have small-data caps; driver-side shared Python quality checks precede Spark joins. This is not a distributed-scale quality engine.
4. The cloud publication job is synchronous; it does not implement a Lambda submit/poll SQL bridge. Query IDs are logged for reconciliation.
5. The cloud mutex has no expiration or automatic takeover. Failure retains it until an operator confirms all jobs and queries stopped. This trades automated recovery for a simpler demonstration of safe serialization.
6. Job retries are disabled for the initial lab because writes use immutable attempts. Recover explicitly with a fresh attempt for pre-publication failures. Replay a committed curated manifest using the publisher's ledger check; do not restart extraction into its existing attempt directory.
7. The local route quarantines new invalid line/payment rows but rejects invalid corrections to existing facts. The cloud route records quarantine then fails the entire batch.
8. SNS exists in the foundation, but notification wiring/subscriptions are not deployed. Configure terminal execution events separately; notification failure must not restart publication.
9. No AWS/Snowflake credentials, selected VPC, budget, or Power BI recording machine were supplied. Account integration evidence, measured costs, cloud dependency lockfiles and runtime compatibility remain pending.

## Acceptance coverage

The local suite covers the mechanics of baseline reconciliation, replay, customer history, completed emptiness, missing/corrupt files, negative quantities, conflicting duplicates, rollback, deletion, backward-watermark rejection, reused-batch protection, invalid corrections and concurrent writers. These local tests are **not** evidence that the corresponding AWS/Snowflake integration cases passed. Test IDs in TEST_PLAN.md remain cloud acceptance targets.

Before presenting this as a deployed end-to-end cloud project, capture actual JDBC/MongoDB job logs, manifest IDs, Parquet schema, Snowflake query IDs and validation results, Step Functions/Airflow terminal state, and dashboard totals. Record exact tested versions and costs. Keep secrets and account-specific evidence out of public commits.
