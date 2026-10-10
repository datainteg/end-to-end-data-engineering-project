"""Glue Spark: validate capped fixture, typed DataFrames and grain-safe sales join.

Driver validation shares local quality rules and is limited to 10,000 records per
dataset. Replace it with distributed validation before increasing that limit.
"""
import hashlib
import json
import sys
from decimal import Decimal
from datetime import datetime
import boto3
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pipeline.contracts import validate, identifier, stamp
from pipeline.local import clean

SCHEMAS = {
 "orders": "order_id string, customer_id string, ordered_at timestamp, status string, currency string, updated_at timestamp, is_deleted boolean",
 "order_items": "order_id string, line_id string, product_id string, quantity long, unit_price decimal(18,2), discount_amount decimal(18,2), updated_at timestamp, is_deleted boolean",
 "payments": "payment_id string, order_id string, amount decimal(18,2), status string, attempted_at timestamp, updated_at timestamp, is_deleted boolean",
 "products": "product_id string, product_name string, category string, updated_at timestamp, is_deleted boolean",
 "customers": "customer_id string, city string, loyalty_tier string, updated_at timestamp, is_deleted boolean",
}


def main():
    args = getResolvedOptions(sys.argv, ["BUCKET", "BATCH_ID", "ATTEMPT_ID", "UPPER_UTC"])
    b, a = identifier(args["BATCH_ID"]), identifier(args["ATTEMPT_ID"])
    s3 = boto3.client("s3")
    bucket = args["BUCKET"]
    manifest = json.loads(s3.get_object(Bucket=bucket, Key=f"raw/batch_id={b}/attempt_id={a}/manifest.json")["Body"].read())
    if (manifest["batch_id"],manifest["attempt_id"],manifest["window_upper_utc"]) != (b,a,args["UPPER_UTC"]):
        raise ValueError("Wrong selected manifest")
    data = {}
    payloads = {}
    def metadata(key):
        head = s3.head_object(Bucket=bucket, Key=key)
        if head["ContentLength"] > 8_000_000:
            raise ValueError("File exceeds demo limit")
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        payloads[key] = body
        return dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
    validate(manifest, metadata)
    for d in manifest["datasets"]:
        rows = [json.loads(line, parse_float=str) for f in d["files"] for line in payloads[f["key"]].splitlines()]
        if len(rows) != d["record_count"] or len(rows) > 10000:
            raise ValueError("Count mismatch or demo limit exceeded")
        if any(stamp(r["updated_at"]) >= stamp(args["UPPER_UTC"]) for r in rows):
            raise ValueError("Record outside upper bound")
        data[d["name"]] = rows
    data, audit, rejected = clean(data)
    # Cloud path is fail-closed: preserve quarantine evidence, then block publication.
    prefix = f"curated/batch_id={b}/attempt_id={a}"
    s3.put_object(Bucket=bucket, Key=f"rejected/batch_id={b}/attempt_id={a}/rows.json", Body=json.dumps(rejected).encode(), IfNoneMatch="*")
    s3.put_object(Bucket=bucket, Key=f"audit/batch_id={b}/attempt_id={a}/quality.json", Body=json.dumps(audit).encode(), IfNoneMatch="*")
    if rejected:
        raise ValueError("Quarantine requires operator correction before cloud publication")
    glue = GlueContext(SparkContext.getOrCreate())
    spark = glue.spark_session
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    frames = {}
    for name, rows in data.items():
        normalized = []
        for source in rows:
            r = dict(source)
            if name == "customers":
                profile = r.pop("profile")
                r.update(city=profile.get("city"), loyalty_tier=profile["loyalty_tier"])
            for k in ["updated_at", "ordered_at", "attempted_at"]:
                if k in r:
                    r[k] = stamp(r[k])
            for k in ["amount", "unit_price", "discount_amount"]:
                if k in r:
                    r[k] = Decimal(str(r[k]))
            normalized.append(r)
        frames[name] = spark.createDataFrame(normalized, SCHEMAS[name])
    sales = frames["order_items"].alias("i").join(frames["orders"].alias("o"), "order_id").join(frames["products"].select("product_id"), "product_id").select(
        F.col("order_id"), F.col("i.line_id").alias("line_id"), F.col("o.customer_id").alias("customer_id"),
        F.col("product_id"), F.col("i.quantity").alias("quantity"),
        (F.col("i.quantity")*F.col("i.unit_price")-F.col("i.discount_amount")).cast("decimal(18,2)").alias("line_revenue"),
        F.col("i.is_deleted").alias("is_deleted"))
    if sales.count() != frames["order_items"].count():
        raise ValueError("Join changed sales grain")
    frames["sales"] = sales
    output = dict(batch_id=b, attempt_id=a, upper_utc=args["UPPER_UTC"], schema_version=1, datasets=[])
    for name, df in frames.items():
        key = f"{prefix}/{name}/"
        df.write.mode("errorifexists").parquet(f"s3://{bucket}/{key}")
        objects = [o for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=key) for o in page.get("Contents", []) if o["Key"].endswith(".parquet")]
        output["datasets"].append(dict(name=name, record_count=df.count(), files=[o["Key"] for o in objects]))
    s3.put_object(Bucket=bucket, Key=f"{prefix}/manifest.json", Body=json.dumps(output).encode(), IfNoneMatch="*")


if __name__ == "__main__":
    main()
