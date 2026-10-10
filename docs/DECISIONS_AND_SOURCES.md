# Decisions, corrections and sources

Prepared 9 October 2026 (Asia/Kolkata). This document preserves the initial design rationale. The original private planning conversation is not part of the public repository. These decisions are not evidence of a deployed system; see [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for current implementation status.

## How the conversation was resolved

| Item | Decision |
| --- | --- |
| Streaming versus batch | Later explicit batch request supersedes early Kafka/Kinesis/PySpark streaming suggestions |
| Architecture | Preserve the later Glue + Lambda + Airflow + Step Functions + Snowflake + Power BI design |
| Duration | Preserve the user's 25–35 minutes; use the supplied nine-chapter 30-minute plan |
| Thumbnail | Preserve the chosen three-element architecture composition and black shirt |
| SQLAlchemy/JDBC | Require a real JDBC source read through Glue; do not call every Python database read JDBC |
| Docker/cloud gap | Local containers do not prove cloud reachability; add a VPC connectivity phase |
| Missing order-line source | Add order_items so product sales has a defined grain |
| Reviews join | Keep reviews separate/aggregated to avoid multiplying sales |
| Incremental join gap | Use complete lookup snapshots and affected-order expansion for the small demo |
| SCD2 | Add explicit close/insert history behavior, deduplication and a publication transaction |
| State/control gap | Propose Snowflake control ledger plus a DynamoDB lease; these are design additions |
| Snowflake invocation gap | Add submit/poll/reconcile bridge rather than implying Step Functions executes SQL automatically |
| Watermark guarantee | Timestamp overlap has limitations; disclose live-source skew and missed intermediate changes |
| BI refresh | Manual post-publication Desktop refresh is the base path; Service automation is an extension |
| Promotional claims | Avoid unsupported production scale, hiring results, retention promises or “free” guarantees |

## Checked primary documentation

These sources support specific implementation constraints; they do not validate our unbuilt implementation. Version selection still requires a tested compatibility matrix.

1. [AWS Glue with Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/connect-glue.html): documents the Glue `.sync` task integration.
2. [Airflow Step Functions operators and sensors](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/operators/step_functions.html): documents starting executions and waiting for terminal state; pin the provider before copying signatures.
3. [Glue JDBC access in a VPC](https://docs.aws.amazon.com/glue/latest/dg/connection-JDBC-VPC.html): connection networking requires subnet/security-group configuration. Our source-host arrangement is a design choice derived from this constraint.
4. [Glue MongoDB connection](https://docs.aws.amazon.com/en_en/glue/latest/dg/creating-mongodb-connection.html): source network reachability and connection configuration must be prepared.
5. [Snowflake S3 storage integrations](https://docs.snowflake.com/en/user-guide/data-load-s3-config-storage-integration): role/trust-based access to approved S3 locations.
6. [Snowflake MERGE](https://docs.snowflake.com/en/sql-reference/sql/merge): duplicate source matches can be nondeterministic or produce duplicate inserts. Source deduplication and the history algorithm are project requirements.
7. [Snowflake transactions](https://docs.snowflake.com/en/sql-reference/transactions): DDL can implicitly commit transactions. Bootstrap objects separately from the DML publication transaction.
8. [Amazon S3 Select availability](https://docs.aws.amazon.com/AmazonS3/latest/userguide/selecting-content-from-objects.html): unavailable to new customers. Replace the transcript's S3 Select recording step with a downloaded small JSON sample or Spark preview.
9. [Power Query Snowflake connector](https://learn.microsoft.com/en-us/power-query/connectors/snowflake): supports Import and DirectQuery with host/authentication considerations. Verify the installed connector and account configuration before recording.
10. [Lambda quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html): standard function timeouts are bounded. The chosen bridge submits/polls rather than waiting inside one long invocation; no “2-second validation” promise is retained.

The transcript's claim that Step Functions executes the workflow “inside the AWS VPC” is replaced by a distinction between managed orchestration and the networking of actual workers. Claims that dual orchestration automatically avoids idle-server cost, or that a basic MERGE alone is SCD2, are not retained.

## Inputs to resolve during implementation

- Actual AWS region, budget, account access and source hosting arrangement.
- Compatible runtime/provider/connector versions and the tested Snowflake bridge authentication method.
- English or Hinglish delivery, channel handle and actual GitHub destination.
- Presenter portrait/recording in a black shirt and final thumbnail asset licenses.
- Power BI Desktop recording machine; Service workspace/permissions only if refresh automation is included.

These inputs do not prevent completion of this planning package. They should be resolved before dependent build or recording steps.
