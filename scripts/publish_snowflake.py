"""Run as python -m scripts.publish_snowflake under the workflow's durable lock.

Batched COPY plus one DML transaction. This bounded demo runner is synchronous,
not the original design's asynchronous submit/poll Lambda bridge.
Secrets Manager JSON supplies Snowflake connector arguments; no SQL credentials
are accepted in Step Functions execution input.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from pipeline.contracts import identifier, stamp

STAGING = {
 "customers": "CUSTOMER_ID VARCHAR,CITY VARCHAR,LOYALTY_TIER VARCHAR,UPDATED_AT TIMESTAMP_NTZ,IS_DELETED BOOLEAN",
 "products": "PRODUCT_ID VARCHAR,PRODUCT_NAME VARCHAR,CATEGORY VARCHAR,UPDATED_AT TIMESTAMP_NTZ,IS_DELETED BOOLEAN",
 "orders": "ORDER_ID VARCHAR,CUSTOMER_ID VARCHAR,ORDERED_AT TIMESTAMP_NTZ,STATUS VARCHAR,CURRENCY VARCHAR,UPDATED_AT TIMESTAMP_NTZ,IS_DELETED BOOLEAN",
 "sales": "ORDER_ID VARCHAR,LINE_ID VARCHAR,CUSTOMER_ID VARCHAR,PRODUCT_ID VARCHAR,QUANTITY NUMBER,LINE_REVENUE NUMBER(18,2),IS_DELETED BOOLEAN",
 "payments": "PAYMENT_ID VARCHAR,ORDER_ID VARCHAR,AMOUNT NUMBER(18,2),STATUS VARCHAR,ATTEMPTED_AT TIMESTAMP_NTZ,UPDATED_AT TIMESTAMP_NTZ,IS_DELETED BOOLEAN",
}
PRIMARY = {"customers":"CUSTOMER_ID", "products":"PRODUCT_ID", "orders":"ORDER_ID", "sales":"ORDER_ID,LINE_ID", "payments":"PAYMENT_ID"}


def run(bucket, batch, attempt, secret_id, lock_table, owner, sql_path):
    import boto3
    import snowflake.connector
    batch, attempt = identifier(batch), identifier(attempt)
    table = boto3.resource("dynamodb").Table(lock_table)
    def check_lock():
        item = table.get_item(Key={"pipeline_id":"ecommerce"}, ConsistentRead=True).get("Item", {})
        if item.get("owner") != owner:
            raise RuntimeError("Execution does not own pipeline lock")
    check_lock()
    s3 = boto3.client("s3")
    prefix = f"curated/batch_id={batch}/attempt_id={attempt}/"
    body = s3.get_object(Bucket=bucket, Key=prefix+"manifest.json")["Body"].read()
    manifest = json.loads(body)
    if (manifest["batch_id"], manifest["attempt_id"], manifest["schema_version"]) != (batch,attempt,1):
        raise ValueError("Wrong curated manifest")
    stamp(manifest["upper_utc"])
    datasets = {d["name"]:d for d in manifest["datasets"]}
    if len(datasets) != len(manifest["datasets"]) or set(datasets) != set(STAGING) | {"order_items"}:
        raise ValueError("Incomplete curated manifest")
    config = json.loads(boto3.client("secretsmanager").get_secret_value(SecretId=secret_id)["SecretString"])
    conn = snowflake.connector.connect(**config)
    queries = []
    try:
        cur = conn.cursor()
        cur.execute("ALTER SESSION SET TIMEZONE='UTC'")
        cur.execute("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=600")
        params = dict(batch=batch, upper=manifest["upper_utc"], hash=hashlib.sha256(body).hexdigest())
        cur.execute("SELECT UPPER_UTC,MANIFEST_HASH FROM BATCH_LEDGER WHERE BATCH_ID=%s", (batch,))
        ledger = cur.fetchall()
        if ledger:
            if len(ledger) != 1 or ledger[0][1] != params["hash"]:
                raise ValueError("Batch already exists with different manifest")
            return dict(status="ALREADY_PUBLISHED",batch_id=batch)
        cur.execute("SELECT MAX(UPPER_UTC) FROM WATERMARKS")
        previous = cur.fetchone()[0]
        if previous and previous >= stamp(manifest["upper_utc"]):
            raise ValueError("Watermark would not advance")
        for name, schema in STAGING.items():
            d = datasets[name]
            if type(d["record_count"]) is not int or not 0 <= d["record_count"] <= 10000:
                raise ValueError("Invalid curated count")
            cur.execute(f"CREATE OR REPLACE TEMP TABLE STG_{name.upper()} ({schema})")
            files = d["files"]
            if len(files) > 1000 or len(set(files)) != len(files) or (d["record_count"] and not files):
                raise ValueError("Invalid curated files")
            selected = []
            for key in files:
                if not key.startswith(prefix+name+"/") or not re.fullmatch(r"[A-Za-z0-9_=/.-]+\.parquet", key) or ".." in key.split("/"):
                    raise ValueError("File outside selected curated dataset")
                selected.append("'"+key.removeprefix("curated/")+"'")
            if selected:
                # Stage is rooted at curated/. File names have a strict character allowlist.
                cur.execute(f"COPY INTO STG_{name.upper()} FROM @ECOMMERCE_CURATED FILES=({','.join(selected)}) FILE_FORMAT=(TYPE=PARQUET USE_LOGICAL_TYPE=TRUE) MATCH_BY_COLUMN_NAME=CASE_INSENSITIVE ON_ERROR=ABORT_STATEMENT")
                queries.append(cur.sfqid)
            cur.execute(f"SELECT COUNT(*) FROM STG_{name.upper()}")
            if cur.fetchone()[0] != d["record_count"]:
                raise ValueError("COPY reconciliation failed")
            cur.execute(f"SELECT COUNT(*) FROM (SELECT {PRIMARY[name]} FROM STG_{name.upper()} GROUP BY {PRIMARY[name]} HAVING COUNT(*)>1)")
            if cur.fetchone()[0]:
                raise ValueError("Duplicate staging keys")
        # Check relationships before joins can silently drop curated records.
        checks = [
            "SELECT COUNT(*) FROM STG_ORDERS O LEFT JOIN STG_CUSTOMERS C ON O.CUSTOMER_ID=C.CUSTOMER_ID WHERE C.CUSTOMER_ID IS NULL",
            "SELECT COUNT(*) FROM STG_SALES S LEFT JOIN STG_ORDERS O ON S.ORDER_ID=O.ORDER_ID LEFT JOIN STG_PRODUCTS P ON S.PRODUCT_ID=P.PRODUCT_ID WHERE O.ORDER_ID IS NULL OR P.PRODUCT_ID IS NULL",
            "SELECT COUNT(*) FROM STG_PAYMENTS P LEFT JOIN STG_ORDERS O ON P.ORDER_ID=O.ORDER_ID WHERE O.ORDER_ID IS NULL",
            "SELECT COUNT(*) FROM STG_SALES WHERE LINE_REVENUE IS NULL OR LINE_REVENUE<0 OR QUANTITY<=0 OR IS_DELETED IS NULL",
            "SELECT COUNT(*) FROM STG_CUSTOMERS WHERE CUSTOMER_ID IS NULL OR LOYALTY_TIER IS NULL OR IS_DELETED IS NULL",
        ]
        for query in checks:
            cur.execute(query)
            if cur.fetchone()[0]:
                raise ValueError("Warehouse staging integrity check failed")
        cur.execute("SELECT COUNT(*) FROM STG_ORDERS S JOIN FACT_ORDERS F ON S.ORDER_ID=F.ORDER_ID JOIN DIM_CUSTOMER C ON F.CUSTOMER_SK=C.CUSTOMER_SK WHERE S.CUSTOMER_ID<>C.CUSTOMER_ID")
        if cur.fetchone()[0]:
            raise ValueError("Order owner change requires explicit restatement")
        check_lock()
        cur.execute("BEGIN")
        try:
            # Authored SQL has no semicolons inside strings or procedure bodies.
            sql = Path(sql_path).read_text()
            sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
            for statement in sql.split(";"):
                if statement.strip():
                    cur.execute(statement, params if "%(" in statement else None)
                    queries.append(cur.sfqid)
            check_lock()
            cur.execute("COMMIT")
        except BaseException:
            conn.rollback()
            raise
        return dict(status="PUBLISHED",batch_id=batch, query_ids=queries)
    finally:
        conn.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ["bucket", "batch-id", "attempt-id", "secret-id", "lock-table", "owner"]:
        p.add_argument("--"+key, required=True)
    p.add_argument("--sql-path", default=str(Path(__file__).resolve().parents[1]/"sql/snowflake/publish.sql"))
    a = p.parse_args()
    print(json.dumps(run(a.bucket,a.batch_id,a.attempt_id,a.secret_id,a.lock_table,a.owner,a.sql_path)))


if __name__ == "__main__":
    main()
