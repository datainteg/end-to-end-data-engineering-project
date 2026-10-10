# Operations, recovery and cost

> Original target design. For the current runnable release, verification results and deliberate simplifications, read [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## Retry and recovery rules

| Event | Required response |
| --- | --- |
| Transient source/network throttling | Bounded exponential retry, new attempt prefix, same logical batch bounds |
| Invalid schema, missing source or quality failure | Stop, preserve raw/quarantine, diagnose; no blind retries or watermark advance |
| Extraction succeeds on one branch only | Preserve completed branch evidence; select explicit attempts when rerunning |
| SQL submit response lost | Reconcile statement handle/operation ledger; inspect active query before resubmission |
| COPY partially executed | Inspect load history and batch staging; reconcile selected files before resuming |
| Publication transaction fails | Roll back DML, retain old watermarks, preserve staging for diagnosis |
| Publication commits but caller times out | Read durable published ledger; return prior success instead of republishing |
| SNS or BI refresh fails after commit | Record follow-up failure and retry that operation; do not roll back published data |
| Duplicate execution or expired lease | Reconcile prior owner and in-flight SQL; reject/serialize before publication |

Proposed initial retry budget: at most three attempts for transient operations, no automatic retries for deterministic data-quality errors. Tune timeout budgets after rehearsal. Confirm what each SDK/operator retries to avoid nested retry multiplication.

Failure record fields: pipeline/batch/attempt ID, stage, exception category, event time, state-machine ARN, Glue job run IDs, SQL query IDs, manifest URI and recovery status. Exclude credentials and complete customer payloads from logs.

## Access matrix

| Identity | Minimum purpose |
| --- | --- |
| Airflow AWS role | Start/describe the chosen state machine; read required execution output |
| Step Functions role | Invoke specified Lambda/Glue jobs and required service-integration actions |
| Extraction role | Read selected secrets/source datasets; write own raw/manifest prefixes |
| Transformation role | Read selected raw inputs; write curated, audit and rejected outputs |
| Validation role | Read manifests and object metadata; bounded read access for samples |
| Loader/control role | Read required secret, selected manifests and lease/control records |
| Snowflake storage integration | Read approved curated S3 locations using scoped trust |
| Snowflake publication role | Load staging and update specified warehouse/control tables |
| Power BI role | Read published analytical views |

Actual policies must be derived from deployed resources and tested API calls. Encrypt source connections and S3, configure key permissions when using customer-managed encryption, and block public bucket access. Storage integration setup follows [Snowflake's S3 integration guide](https://docs.snowflake.com/en/user-guide/data-load-s3-config-storage-integration).

## Cost worksheet to fill before deployment

Record region, currency, pricing-check date, daily run count, retention and maximum development spend. Estimate Glue worker-hours, source host/database hours, S3 storage/requests, logs, Lambda, Step Functions transitions, Secrets Manager, network egress/NAT/endpoints, lease table, Snowflake credits/storage and any Power BI license/capacity. Check current account offers; no free-tier/trial duration is assumed.

Use AWS spend alerts, short development log retention, resource tags and expiry dates. Use Snowflake auto-suspend and an appropriate resource monitor for the warehouse. Alerts are not a universal instantaneous hard spending cap. Record actual rehearsal costs next to the estimate before presenting cost claims.

## Teardown sequence

1. Disable the Airflow schedule and any dashboard automation; identify active executions.
2. Stop or let owned jobs/queries finish; reconcile the last publication and release the lease safely.
3. Retain sanitised evidence and the final repository release needed to reproduce the tutorial.
4. Remove temporary compute, database hosts, Glue jobs/connections, functions, workflows and project-only network components through the chosen infrastructure tool.
5. Remove project-only secrets and IAM trust/grants according to the environment's retention plan.
6. Suspend/remove project Snowflake compute and demo objects when no longer needed.
7. Review S3 object versions, multipart uploads, logs, snapshots and network resources that can continue costing money.
8. Verify the remaining resource inventory and billing view. Delete data only after selecting what demonstration evidence to retain.

## Manual recovery runbook

Locate the batch ledger first. If PUBLISHED, repair only notifications/BI. Otherwise identify the failed phase and inspect its selected manifests/query handles. Correct configuration or source data, create a new attempt where needed, and rerun from a documented boundary under the same serialized publication contract. Reconcile counts and dashboard totals before marking recovery complete.
