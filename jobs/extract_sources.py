"""AWS Glue Spark job: frozen-source full snapshots through JDBC and MongoDB.

Upload pipeline.zip using --extra-py-files. Configure both Glue connections on job.
This small-fixture implementation writes JSONL and refuses more than 10,000 rows
per source; it is intentionally not a scalable incremental extractor.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
import boto3
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pipeline.contracts import identifier, stamp, digest
from pipeline.fixture import DATASETS


def main():
    args = getResolvedOptions(sys.argv, ["BUCKET", "BATCH_ID", "ATTEMPT_ID", "UPPER_UTC", "PG_CONNECTION", "MONGO_CONNECTION"])
    batch, attempt = identifier(args["BATCH_ID"]), identifier(args["ATTEMPT_ID"])
    upper = stamp(args["UPPER_UTC"])
    glue = GlueContext(SparkContext.getOrCreate())
    glue.spark_session.conf.set("spark.sql.session.timeZone", "UTC")
    s3 = boto3.client("s3")
    base = f"raw/batch_id={batch}/attempt_id={attempt}"
    manifest = dict(schema_version=1, pipeline_id="ecommerce", batch_id=batch, attempt_id=attempt,
                    window_upper_utc=args["UPPER_UTC"], created_at=datetime.now(timezone.utc).isoformat(), datasets=[])
    for name in DATASETS:
        if name == "customers":
            frame = glue.create_dynamic_frame.from_options(connection_type="mongodb", connection_options={
                "connectionName": args["MONGO_CONNECTION"], "database": "ecommerce", "collection": "customers"}).toDF().drop("_id")
        else:
            frame = glue.create_dynamic_frame.from_options(connection_type="postgresql", connection_options={
                "useConnectionProperties": "true", "connectionName": args["PG_CONNECTION"], "dbtable": f"public.{name}"}).toDF()
        # Full snapshot route requires frozen sources; fail instead of quietly dropping future edits.
        if frame.filter(F.col("updated_at") >= F.lit(upper)).limit(1).count():
            raise ValueError("Source changed at/after batch upper bound; freeze fixture and use a new upper bound")
        rows = frame.limit(10001).toJSON().collect()
        if len(rows) > 10000:
            raise ValueError("Teaching snapshot row cap exceeded")
        parsed = [json.loads(r, parse_float=str) for r in rows]
        content = "".join(json.dumps(r, sort_keys=True) + "\n" for r in parsed).encode()
        files = []
        if rows:
            key = f"{base}/dataset={name}/part-00000.jsonl"
            sha = hashlib.sha256(content).hexdigest()
            s3.put_object(Bucket=args["BUCKET"], Key=key, Body=content, IfNoneMatch="*", Metadata={"sha256":sha})
            files.append(dict(key=key, bytes=len(content), sha256=sha))
        manifest["datasets"].append(dict(name=name, source="mongodb" if name == "customers" else "postgresql",
            mode="snapshot", lower_utc="1970-01-01T00:00:00Z", upper_utc=args["UPPER_UTC"], status="COMPLETE",
            schema_fingerprint=digest(sorted(parsed[0]) if parsed else frame.columns), record_count=len(rows), files=files))
    s3.put_object(Bucket=args["BUCKET"], Key=f"{base}/manifest.json", Body=json.dumps(manifest).encode(), IfNoneMatch="*")
    print(json.dumps({"batch_id": batch, "attempt_id": attempt, "manifest_key": f"{base}/manifest.json"}))


if __name__ == "__main__":
    main()
