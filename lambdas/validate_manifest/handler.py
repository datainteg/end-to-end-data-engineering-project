"""Bounded small-demo manifest validator. Package with the pipeline directory."""
import hashlib
import json
import os
from pipeline.contracts import validate, identifier


def handler(event, context):
    import boto3
    s3 = boto3.client("s3")
    bucket = os.environ["PROJECT_BUCKET"]  # Never accept arbitrary buckets from payload.
    batch, attempt = identifier(event["batch_id"]), identifier(event["attempt_id"])
    key = f"raw/batch_id={batch}/attempt_id={attempt}/manifest.json"
    response = s3.get_object(Bucket=bucket, Key=key)
    if response["ContentLength"] > 1_000_000:
        raise ValueError("Manifest too large")
    manifest = json.loads(response["Body"].read())
    if manifest["batch_id"] != batch or manifest["attempt_id"] != attempt or manifest["window_upper_utc"] != event["upper_utc"]:
        raise ValueError("Manifest does not belong to the selected execution")
    if len(manifest.get("datasets", [])) != 5 or sum(len(d["files"]) for d in manifest["datasets"]) > 20:
        raise ValueError("Small-demo file cap exceeded")
    budget = 0
    def metadata(k):
        nonlocal budget
        head = s3.head_object(Bucket=bucket, Key=k)
        budget += head["ContentLength"]
        if budget > 32_000_000:
            raise ValueError("Small-demo 32 MB validation cap exceeded")
        body = s3.get_object(Bucket=bucket, Key=k)["Body"].read()
        return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    validate(manifest, metadata)
    return {"manifest_key": key, "status": "VALIDATED"}
