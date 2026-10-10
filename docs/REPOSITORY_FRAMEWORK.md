# Implementation framework

> Original target design. For the current runnable release, verification results and deliberate simplifications, read [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

This is a proposed future implementation layout, not a claim that the following source files exist. The current delivery is the planning package. Add runnable files when their phase begins; do not fill the tree with misleading `pass` implementations.

```text
data_engineering_1_project/
  README.md, BRIEF.md, REQUIREMENTS.md, TRACKER.md
  docs/                         architecture, contracts, operations and tests
  infra/                        network, IAM, S3, Glue, Lambda, SNS, lease table
  local/docker-compose.yml      local source databases and Airflow
  config/dev.example.yaml       region, names, bounds, limits; no secrets
  .env.example                  connection/secret references only
  requirements.in               selected direct Python dependencies
  requirements.lock             tested resolved versions for local tools
  sources/postgresql/           schema, seed and controlled mutations
  sources/mongodb/              seed and controlled mutations
  jobs/extract_postgresql.py     actual Glue JDBC reads
  jobs/extract_mongodb.py        Glue MongoDB reads
  jobs/transform_curated.py      explicit schema, quality and joins
  lambdas/batch_control/         lease, batch initialization and control reads
  lambdas/validate_manifest/     bounded metadata checks
  lambdas/snowflake_bridge/      submit, poll, reconcile and cancel SQL
  orchestration/airflow/dags/    schedule and Step Functions start/wait
  orchestration/step_functions/  Standard state machine definition
  schemas/                      manifests and dataset schema versions
  sql/bootstrap/                roles, stages, formats, tables, views
  sql/load/                     batch COPY and reconciliation
  sql/publish/                  SCD2, fact changes, ledger and watermarks
  sql/validation/               uniqueness, sums and history assertions
  tests/fixtures/               baseline, update, invalid and replay cases
  tests/unit/                   pure validation and business-rule checks
  tests/integration/            real AWS/Snowflake evidence, isolated data
  tools/                        seed/reset, validation and release helpers
  powerbi/                      report, measures and model instructions
  video/                        timeline, frames, script and packaging
  assets/                       licensed fonts/logos and presenter portrait
  recordings/raw/               original screen/camera takes
  voiceover/                    original narration clips and mapping
  exports/                      measured captions, review frames and MP4
```

## Configuration contract

Required configuration: environment, AWS region, bucket, pipeline ID, source connection names/secret ARNs, Glue job names, state machine ARN, SNS topic, lease table, Snowflake account/role/warehouse/database/schema, stage name, schema version, extraction overlap, timeouts and allowed attempt count. Use UTC batch bounds independently of the presenter's local recording timezone.

Every job accepts batch ID, attempt ID, selected manifest URI, schema version and bounds as relevant. Return identifiers, counts, status and output URIs. Do not return source payloads or passwords to Airflow XCom or Step Functions state.

Pin each execution environment separately: Glue runtime and supported connector/JAR versions differ from local Airflow's dependency lock. Record the exact provider APIs used. The pasted `schedule_interval`/`SnowflakeOperator` sample is historical pseudocode, not a version-validated implementation.

## Naming and contributor contract

- Use a stable batch ID for a logical window/replay and a separate attempt ID for retry outputs.
- Keep schema/business rules shared between extraction, transformation and validation where practical.
- SQL files accept explicit batch/attempt identifiers and validated identifiers; parameterize values rather than interpolate untrusted SQL.
- Keep secrets, local environment files, state files containing credentials, recordings and generated exports out of public source control.
- Add a license before making the repository public; retain third-party asset licenses.
- Release checklist: tested versions, setup, seed, run, verify, troubleshoot and teardown all documented.
