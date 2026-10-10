# Cloud integration lab

This is an account-specific lab, not a one-command production deployment. The Python/SQLite route is verified separately. Cloud code is supplied but has not been executed against your AWS/Snowflake accounts. Follow this guide in a temporary development environment and record evidence at each checkpoint.

## 1. Choose the environment

Select an AWS region, budget, source VPC/subnets/security groups, Snowflake account/database/schema/warehouse, and an Airflow host. Set resource expiry tags and billing alerts. Use a small Snowflake warehouse with auto-suspend; record actual costs instead of assuming free usage.

Host PostgreSQL and MongoDB where Glue can reach them privately, with TLS and read-only extraction credentials. The loopback Docker setup is a local exercise only. Configure source indexes from the DDL/seed script and freeze writes during each teaching batch.

Candidate runtime: Glue 5.0, Python 3.11 Lambda, PostgreSQL 16.6, MongoDB 7.0.16. `requirements-cloud.txt` and `requirements-sources.txt` pin candidate direct dependencies; they are not a tested cloud lockfile. Select compatible Airflow core/Amazon provider versions using their official constraints. Do not install Airflow into the offline reference environment.

## 2. Create the foundation

Review `infra/foundation.yaml`, then deploy with your selected AWS profile:

```bash
aws cloudformation deploy --stack-name ecommerce-demo-foundation \
  --template-file infra/foundation.yaml
aws cloudformation describe-stacks --stack-name ecommerce-demo-foundation \
  --query 'Stacks[0].Outputs'
```

Record the bucket and lock table outputs in ignored `config/dev.local.json`, copied from `config/cloud.example.json`. The bucket and lock table have retention policies; deleting the stack does not automatically erase them. No source hosts, network, IAM service roles, Glue connections/jobs, Lambda functions or state machine are created by this foundation.

## 3. Prepare IAM, networking and credentials

Use distinct service roles and only project resource ARNs:

| Role | Required access |
| --- | --- |
| Extract Glue | Read its connection secrets; source network access; read release scripts; put `raw/*`; CloudWatch logs |
| Transform Glue | Read selected raw/release paths; list selected prefixes; write `curated/*`, `rejected/*`, `audit/*`; logs |
| Publish Glue | Read selected curated manifest and SQL; read Snowflake secret; consistent GetItem on mutex; logs; Snowflake network access |
| Validator Lambda | GetObject and HeadObject on raw; logs |
| Lock Lambda | Conditional PutItem/DeleteItem on the mutex table; logs |
| Step Functions | Invoke the two functions; Glue StartJobRun/GetJobRun/GetJobRuns/BatchStopJobRun on the selected jobs and required integration permissions |
| Airflow | StartExecution and DescribeExecution for the chosen workflow |
| Snowflake storage role | Read only curated objects, constrained ListBucket, trusted integration principal + external ID |
| BI Snowflake role | Warehouse usage and SELECT on published marts/model tables only |

Glue jobs in a VPC need routing/DNS, database ingress from Glue's security group, S3 access and access to Secrets Manager and relevant service endpoints. Provide Snowflake egress for the publisher. Include ENI creation/use permissions where required by Glue VPC jobs. Configure CloudWatch log retention.

Create named Glue PostgreSQL and MongoDB connections with secret references and TLS settings. Put **both connections** on the extraction job. MongoDB connection options are resolved through `connectionName`. First test a tiny actual read with `jobs/extract_sources.py`; local Python database connectivity does not prove Glue JDBC connectivity.

Store Snowflake connector options in Secrets Manager: `account`, `user`, `role`, `warehouse`, `database`, `schema`, and your account-approved authentication fields. For service authentication use supported key-pair/OAuth configuration; do not place secrets in workflow input or commit the JSON. Ensure the configured auth works from the chosen Glue runtime before running publication.

## 4. Bootstrap Snowflake

Use an administrator to create a project database/schema, a publisher role, BI role and warehouse. Select the project context in a SQL worksheet. Execute `sql/snowflake/storage_integration.sql` after replacing placeholders locally. Follow `DESC INTEGRATION` to configure the AWS trust principal and external ID, then grant the publisher stage usage.

Execute `sql/snowflake/bootstrap.sql`. Keep DDL outside publication transactions. The stage named `ECOMMERCE_CURATED` must point exactly to `s3://YOUR_BUCKET/curated/`; the loader removes this prefix from manifest keys.

Snowflake standard table key declarations do not replace writer serialization or staging uniqueness checks. Restrict target-table DML to the workflow's publisher role. Do not run an independent publisher bypassing the durable mutex.

## 5. Package code and create jobs

```bash
python3 scripts/package_cloud.py
# Set PROJECT_BUCKET to your foundation bucket first.
aws s3 cp .runtime/packages/pipeline.zip "s3://$PROJECT_BUCKET/scripts/v0.1.0/pipeline.zip"
aws s3 cp jobs/ "s3://$PROJECT_BUCKET/scripts/v0.1.0/jobs/" --recursive
aws s3 cp sql/snowflake/publish.sql "s3://$PROJECT_BUCKET/scripts/v0.1.0/sql/publish.sql"
```

Create three Glue Spark jobs using their matching files: `extract_sources.py`, `transform_curated.py`, `publish_warehouse.py`. Configure `--extra-py-files` with the uploaded `pipeline.zip` on each job, job timeout at most 30 minutes, concurrent runs 1, and automatic retries 0. Pick supported small worker settings in your region. Attach VPC connections as needed. For the publish job install a compatible `snowflake-connector-python` via `--additional-python-modules`; test the candidate pin before recording.

Extraction accepts `BUCKET`, `BATCH_ID`, `ATTEMPT_ID`, `UPPER_UTC`, `PG_CONNECTION`, `MONGO_CONNECTION`. Transform uses the first four. The publisher additionally uses `SNOWFLAKE_SECRET`, `LOCK_TABLE`, `OWNER`, `PUBLISH_SQL_KEY`; the workflow supplies these values. SDK/JDBC/Mongo connector compatibility must be verified in the actual job runtime.

Create two Python 3.11 Lambda functions from `.runtime/packages/validate_manifest.zip` and `pipeline_lock.zip`, handler `handler.handler`. Set validator `PROJECT_BUCKET` and lock function `LOCK_TABLE`. Use a 60-second validator timeout and suitable memory for its 32 MB read cap. Grant only the table/bucket permissions above. Do not accept arbitrary bucket names from a Lambda invocation.

## 6. Create and start Step Functions

Fill the Lambda ARNs/job names in `config/dev.local.json`:

```bash
python3 scripts/build_state_machine.py --config config/dev.local.json
```

Create a **Standard** state machine using `.runtime/state-machine.json` and the scoped workflow role. Enable execution logging without source payloads/secrets. The workflow acquires a non-expiring lock, runs extraction, validates, transforms, publishes and releases the lock after success. Failure after acquisition leaves the lock held. No automatic retry is configured for immutable writes.

Example execution input (use a fresh attempt ID each new extraction):

```json
{"batch_id":"baseline-001","attempt_id":"attempt-001","upper_utc":"2026-01-02T00:00:00Z"}
```

This bound matches the deterministic baseline fixture; real source edits require a later UTC upper bound. Freeze writers. Watch job and query IDs. Run `sql/snowflake/validate.sql` after success. Expected baseline KPI row: 1200, 2, 600, 0.5.

## 7. Configure Airflow and terminal notifications

Install a compatible Airflow core/Amazon provider pair with official constraints in a separate environment. Copy `orchestration/airflow/dags/ecommerce_batch.py` into its DAG directory, set `STATE_MACHINE_ARN`, and configure `aws_default` using a role/profile. Validate the DAG imports before use. It has no automatic schedule; trigger with the three execution fields above. The terminal sensor must fail if AWS reports a failed or timed-out execution. Test this deliberately.

For notifications, configure an EventBridge rule for this state machine's terminal execution events and send to the foundation SNS topic; permit EventBridge to publish only from that rule and confirm your subscription. This optional account wiring is not in the supplied foundation template. Alert processing must not call the data publication workflow again.

## 8. Replay and recover safely

- On success, use the **original curated manifest** and batch ID for a publication-only replay under a newly acquired owner lock. Call the publish job directly with that owner and original attempt. The ledger returns `ALREADY_PUBLISHED`. Do not rerun extraction into an existing immutable attempt.
- On failure, inspect Step Functions, Glue jobs, Snowflake running queries and the batch ledger. A timed-out client does not prove the SQL transaction failed.
- If committed, repair only the follow-up action. If not committed, confirm all old jobs/queries stopped before deleting the lock item; then begin a fresh attempt. The original batch ID can be used only if it has not committed.
- Never release a lock on a timer. An operator must reconcile the previous owner's queries first. Restrict DeleteItem to that recovery role and lock function.
- Change the synthetic customer tier, then use a new batch ID and later upper bound. Verify one current customer version and unchanged fact attribution.

## 9. Report and teardown

Build the report using `powerbi/README.md`, refresh only after publication and reconcile with SQL. Capture evidence in ignored `.runtime/evidence/`. Record tested versions, counts, costs and query IDs in a sanitized release report.

Stop Airflow triggers and active executions first. Reconcile running jobs/queries, remove project jobs/functions/workflow and temporary source/network resources, suspend/delete the project Snowflake warehouse as appropriate, then remove project secrets/trust grants. Delete retained S3 versions and DynamoDB only after choosing what evidence to keep. Review logs, endpoints/NAT, volumes and snapshots for continuing charges.

## Official references checked for this implementation

- [Glue MongoDB connections](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-connect-mongodb-home.html): connection configuration and `connectionName`.
- [Glue JDBC VPC networking](https://docs.aws.amazon.com/glue/latest/dg/connection-JDBC-VPC.html): private database reachability.
- [Step Functions Glue integration](https://docs.aws.amazon.com/step-functions/latest/dg/connect-glue.html): synchronous job tasks.
- [Airflow Step Functions integration](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/operators/step_functions.html): start operator and terminal sensor.
- [Snowflake COPY INTO](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table): selected file loading and column matching.
- [Snowflake Python connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-example): execution/query IDs and client behavior.

Documentation checks support the API choices; they do not certify this account-specific integration.
