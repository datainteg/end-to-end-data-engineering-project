[← Project home](../README.md) · [All docs](README.md) · [Hands-on tutorial](../tutorial/WALKTHROUGH.md) · [Interview questions](INTERVIEW_QUESTIONS.md)

# 💻 Code tour: follow one batch

**Read this beside `pipeline/local.py`.** The offline reference uses ordinary Python, exact money arithmetic and SQLite so you can inspect the full publication boundary.

![Working local reference](diagrams/local-reference.svg)

## 1. Start with the business data

Open [fixture.py](../pipeline/fixture.py). `baseline()` creates orders, order items, payments, products and customer profiles. `changed()` changes C001's loyalty tier for a later observed batch. Source timestamps are fixed for a reproducible demonstration.

**Question to answer:** why are there three order lines but four payment attempts?

Because one order has two attempts. Payment attempts are not additional sales. The baseline has two paid orders and one cancelled order.

## 2. Store an attempt before transforming it

Open `extract()` in [local.py](../pipeline/local.py). It validates batch/attempt IDs, creates a new attempt directory, writes JSONL, computes file hashes and finally writes the manifest.

```text
batch_id = logical publication
attempt_id = one extraction attempt
manifest = explicit evidence of its selected inputs
```

`exist_ok=False` prevents reusing the same local attempt directory. The upper-bound check rejects a snapshot containing later records. This release archives complete teaching snapshots; it does not filter source deltas using committed watermarks.

**Read next:** `read_attempt()` and [contracts.validate()](../pipeline/contracts.py). They check file integrity and reconcile declared counts before business processing.

## 3. Make quality decisions explicit

`clean()` validates required fields and keys, detects duplicate conflicts, chooses the latest observed record by key, checks business rules and verifies references. Its result includes accepted records, per-dataset counts and rejected rows with reasons.

| Input condition | Local behavior |
| --- | --- |
| Exact duplicate | Collapse it and count it as a duplicate |
| Newer version of the same key | Keep the later version |
| Same key/time, different payload | Fail because the choice is ambiguous |
| New line with negative quantity | Quarantine it with a reason |
| Invalid correction to an existing fact | Block publication inside `publish()` |
| Missing required field or broken reference | Fail before publication |

The [cloud transform](../jobs/transform_curated.py) shares the bounded cleaning rules, then builds explicitly typed Spark frames. It writes rejection evidence but blocks publication for any quarantine.

## 4. Find the transaction boundary

`publish()` calls validation and cleaning first. It then opens the warehouse and starts `BEGIN IMMEDIATE`, which serializes local database writers.

Read the function in this order:

1. **Ledger check:** already committed accepted content and bounds return `ALREADY_PUBLISHED`; changed content under the same ID fails.
2. **Watermark check:** a new publication must advance the committed upper bound.
3. **Customer history:** close a changed current version and insert the new observation.
4. **Dimensions and facts:** upsert separate product, date, order, sales and payment grains.
5. **Invalid-correction check:** refuse to silently keep an old fact while accepting an invalid replacement.
6. **Control updates:** insert quality counts, new watermarks and the batch ledger.
7. **Commit or rollback:** publish the transaction, or roll it back when an exception occurs.

S3/filesystem audit writes are outside database atomicity. The ledger is authoritative for committed publication. Cloud SQL has a similar intended business commit boundary, but its actual execution still requires integration validation.

## 5. Inspect customer attribution

In `DIM_CUSTOMER`, `customer_id` identifies a customer while `customer_sk` identifies an observed version. A change from Silver to Gold closes one row and opens another. The fact upsert preserves the existing customer key rather than reclassifying historical facts.

**Correct interpretation:** “tier observed at first publication.” This is not complete customer change history or proof of the tier at original order time.

## 6. Verify exact money and metrics

`money()` validates a nonnegative two-decimal amount and returns integer paise. `metrics()` reads the published warehouse and formats rupee outputs.

```python
from pipeline.local import money

line_paise = 2 * money("500.00") - money("100.00")
assert line_paise == 90000
```

`mart_sales` excludes cancelled/deleted orders and deleted lines. Paid-order count uses order headers. Payment success uses payment attempts. Keep these definitions consistent with the [Power BI measures](../powerbi/measures.dax).

## 7. Let the tests explain the guarantees

Open [test_pipeline.py](../tests/test_pipeline.py) and read the action and expected outcome before the implementation details.

| Read this test | What it demonstrates |
| --- | --- |
| `test_baseline_replay_and_customer_history` | Correct metrics, safe replay and stable fact attribution |
| `test_rollback_preserves_targets_and_watermarks` | No partial customer or control changes after injected failure |
| `test_missing_or_corrupted_file_blocks_publication` | Incomplete evidence stops the batch |
| `test_invalid_correction_does_not_hide_stale_fact` | An invalid replacement cannot silently advance publication |
| `test_writer_lock_prevents_concurrent_publication` | Competing local writers are serialized |

## 8. Map the local concepts to cloud files

| Local concept | Cloud counterpart | What still needs proof |
| --- | --- | --- |
| Fixture and snapshot extraction | [Glue extraction](../jobs/extract_sources.py) | Real JDBC/MongoDB connectivity and source consistency |
| Manifest validation | [Validator Lambda](../lambdas/validate_manifest/handler.py) | Deployed permissions, limits and failure propagation |
| Cleaning and typed output | [Spark transform](../jobs/transform_curated.py) | Glue runtime behavior and Parquet output |
| SQLite writer transaction | [Snowflake runner](../scripts/publish_snowflake.py) + [DML](../sql/snowflake/publish.sql) | Real COPY, transaction and recovery tests |
| Local writer serialization | [DynamoDB mutex Lambda](../lambdas/pipeline_lock/handler.py) | Account-level acquisition and recovery behavior |
| Manual CLI commands | [Airflow DAG](../orchestration/airflow/dags/ecommerce_batch.py) + [ASL example](../orchestration/step_functions/state-machine.example.json) | Terminal success/failure propagation |

[Next: run the hands-on lessons →](../tutorial/WALKTHROUGH.md) · [Practice explaining these choices →](INTERVIEW_QUESTIONS.md)
