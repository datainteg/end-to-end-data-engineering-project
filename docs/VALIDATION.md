# Executed validation

Executed 10 October 2026 (Asia/Kolkata) in the project workspace. These results cover local code and isolated source containers. They do not claim a deployed cloud pipeline.

## Environment

- Python 3.12.3; local pipeline uses only the standard library.
- Docker Engine 29.6.1 and Compose v5.2.0.
- PostgreSQL container image `postgres:16.6`; MongoDB image `mongo:7.0.16`.
- Source clients: psycopg/psycopg-binary 3.2.3 and pymongo 4.10.1. Resolved installed packages are in `requirements-sources.lock.txt`.
- CI is configured for Python 3.11 and 3.12; a configured workflow is not evidence of a GitHub-hosted run.

## Results

| Check | Observed result |
| --- | --- |
| `python3 -m unittest discover -s tests -v` | 12 tests passed |
| Fresh local baseline | PUBLISHED, sales 1200.00, paid orders 2, AOV 600.00, attempt rate 0.5000 |
| Same-manifest replay | ALREADY_PUBLISHED; unchanged totals |
| Customer change | Three total customer versions, two current; original fact keys retained |
| Injected failures after dimensions and before commit | Target changes and watermarks rolled back |
| Missing/corrupt files, bad references, schema errors | Publication blocked |
| Empty completed snapshot | Accepted; all five publication watermarks recorded |
| Conflicting duplicates, batch reuse, backward watermark | Rejected |
| Negative quantity, invalid correction, soft deletion | Expected quality or metric behavior verified |
| Concurrent writer | Second writer blocked by database transaction lock |
| Isolated source containers | Both health checks passed |
| PostgreSQL seed | Orders 3, lines 3, attempts 4, products 3; independent SQL sales 1200.00; successful attempts 2 of 4 |
| Seed replay | Same source counts and totals; no duplicate fixture keys |
| MongoDB seed and mutation | Two customers with BSON datetime timestamps; C001 changed Silver → Gold |
| Fresh export of tracked files | Baseline and replay succeeded without ignored/private workspace files |
| Python compilation | Pipeline, jobs, Lambdas, scripts and DAG files compiled |
| Cloud packaging | Project/Lambda ZIPs generated; project package imports resolved from ZIP |
| Step Functions generation | Example JSON generated from configuration |
| Public file review | No runtime credentials, private paths, raw media or private planning files staged; nine public narration scripts included |

The source tests used an isolated Compose project on ports 15432/27027 so an existing database service was not touched. Test containers, network and volumes were removed after verification. Raw execution data and generated packages remain ignored.

## Still not executed

AWS deployment, actual Glue JDBC/MongoDB reads, Glue runtime compatibility, PySpark execution, Lambda integration, Snowflake COPY/publication, Airflow runtime import/terminal propagation, SNS delivery, Power BI report reconciliation, audio recording and final video export. The full target acceptance matrix in TEST_PLAN.md remains integration work; local analogues do not satisfy cloud evidence requirements.

Reproduce the checked path with `docs/GETTING_STARTED.md`; use `docs/CLOUD_SETUP.md` for the next integration stage.
