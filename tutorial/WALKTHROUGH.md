[← Tutorial hub](README.md) · [Project home](../README.md) · [Code tour](../docs/CODE_TOUR.md) · [Interview guide](../docs/INTERVIEW_QUESTIONS.md)

# 🚀 Hands-on walkthrough

**Goal:** run a batch, understand the numbers, inspect history and prove failure recovery. Use Python 3.11+ from the repository root. The local lessons do not require third-party packages, Docker or cloud accounts.

[1. Run](#lesson-1-run-and-reconcile) → [2. Inspect](#lesson-2-read-the-warehouse) → [3. Replay](#lesson-3-replay-and-observe-history) → [4. Test failure](#lesson-4-test-failure-and-recovery) → [5. Map to cloud](#lesson-5-map-to-the-cloud)

## Lesson 1: run and reconcile

```bash
python3 -m pipeline.local demo --root .runtime/tutorial
```

A fresh run prints `PUBLISHED`, then `ALREADY_PUBLISHED`. Both steps refer to the same logical baseline publication. Later runs report the batch as already published.

| Result | Expected | Explain it yourself |
| --- | --- | --- |
| Demo net sales | `1200.00` | O100 contributes 900; O101 contributes 300 |
| Paid orders | `2` | The cancelled order is excluded |
| AOV | `600.00` | 1200 / 2 |
| Payment success | `0.5000` | 2 successful attempts / 4 total attempts |

**Checkpoint:** explain why O101's failed and successful attempts do not create two sales lines. Read [fixture.py](../pipeline/fixture.py) before moving on.

## Lesson 2: read the warehouse

```bash
python3 - <<'PY'
from pipeline.local import connect

db = connect('.runtime/tutorial')
try:
    for table in ['fact_orders', 'fact_sales', 'fact_payments',
                  'dim_customer', 'batch_ledger', 'watermarks']:
        print(table, db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
    print('Published sales lines:')
    for row in db.execute('SELECT order_id, line_id, revenue_paise FROM mart_sales ORDER BY order_id'):
        print(row)
finally:
    db.close()
PY
```

After a fresh baseline, expect 3 order headers, 3 sales lines, 4 payment attempts, 2 customer versions, 1 ledger row and 5 watermarks. The sales view has two rows, with `90000` and `30000` paise. A cancelled order can remain in a fact table while being excluded from the business view.

Use the [warehouse model](../docs/diagrams/warehouse-model.svg) to identify each row's grain. If you already completed lesson 3, customer-version and ledger counts will be higher; rerunning a lesson does not reset the warehouse.

**Checkpoint:** describe the difference between a row in `FACT_SALES` and a row in `MART_SALES`.

## Lesson 3: replay and observe history

```bash
python3 -m pipeline.local demo --root .runtime/tutorial
python3 -m pipeline.local customer-change --root .runtime/tutorial
```

The repeated baseline does not add facts. The change creates a new Gold observation for C001 while keeping its old Silver version. Query both the versions and existing fact attribution:

```bash
python3 - <<'PY'
from pipeline.local import connect

db = connect('.runtime/tutorial')
try:
    for row in db.execute('''
        SELECT customer_id, loyalty_tier, is_current, valid_from, valid_to
        FROM dim_customer ORDER BY customer_id, valid_from
    '''):
        print(row)
    print('Existing fact attribution:')
    for row in db.execute('''
        SELECT s.order_id, c.customer_id, c.loyalty_tier
        FROM fact_sales s JOIN dim_customer c USING (customer_sk)
        ORDER BY s.order_id
    '''):
        print(row)
finally:
    db.close()
PY
```

C001 has two versions and one current row. Existing C001 sales still reference Silver. The metric output remains ₹1,200 / 2 / ₹600 / 50%.

**Checkpoint:** explain why this is observed batch history, not guaranteed customer history at the original order time.

## Lesson 4: test failure and recovery

Run the isolated behavioral tests. They use temporary warehouses and do not reset your tutorial data.

```bash
# Failure after dimensions and before commit
python3 -m unittest discover -s tests -k rollback -v

# Missing or corrupt input files
python3 -m unittest discover -s tests -k missing_or_corrupted -v

# All correctness and failure cases
python3 -m unittest discover -s tests -v
```

Read the matching tests in [test_pipeline.py](../tests/test_pipeline.py). A successful test means it observed the required behavior, not that it hid the injected failure. Rollback must preserve both business tables and committed watermarks.

To perform a visible missing-file demonstration yourself, follow [setup guide step 5](../docs/GETTING_STARTED.md#5-demonstrate-failed-validation-and-recovery). That example uses a separate scratch warehouse.

**Checkpoint:** answer this without looking: if extraction completed but publication failed, should the committed watermark advance? Why?

## Lesson 5: map to the cloud

Read the [cloud workflow](../docs/diagrams/cloud-workflow.svg) and compare the implementation with the local path:

| Same idea | Cloud implementation to inspect |
| --- | --- |
| Archive selected evidence | [Glue extractor](../jobs/extract_sources.py) |
| Validate before processing | [Manifest Lambda](../lambdas/validate_manifest/handler.py) |
| Type, clean and preserve grain | [Spark transform](../jobs/transform_curated.py) |
| Stage selected files and commit business state | [Snowflake publisher](../scripts/publish_snowflake.py) |
| Coordinate and wait for the result | [Step Functions example](../orchestration/step_functions/state-machine.example.json) |

Do not start cloud resources until you have selected accounts, connectivity and a cost budget. The [cloud setup guide](../docs/CLOUD_SETUP.md) provides the dependency order and teardown directions. The [advanced page](../docs/diagrams/advanced-roadmap.svg) describes future improvements, not additional working code.

**Final exercise:** explain the project in one minute, then pick one failure scenario and show the code/test evidence. Use the [interview guide](../docs/INTERVIEW_QUESTIONS.md) to practice.

---

[← Tutorial hub](README.md) · [Read the code tour](../docs/CODE_TOUR.md) · [Record a walkthrough](RECORDING.md) · [Browse all docs](../docs/README.md)
