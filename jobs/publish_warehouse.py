"""Glue Spark driver wrapper; package scripts and pipeline in pipeline.zip."""
import sys
from pathlib import Path
import boto3
from awsglue.utils import getResolvedOptions
from scripts.publish_snowflake import run
import json

args = getResolvedOptions(sys.argv, ["BUCKET", "BATCH_ID", "ATTEMPT_ID", "SNOWFLAKE_SECRET", "LOCK_TABLE", "OWNER", "PUBLISH_SQL_KEY"])
path = Path("/tmp/ecommerce-publish.sql")
boto3.client("s3").download_file(args["BUCKET"], args["PUBLISH_SQL_KEY"], str(path))
print(json.dumps(run(args["BUCKET"],args["BATCH_ID"],args["ATTEMPT_ID"],args["SNOWFLAKE_SECRET"],args["LOCK_TABLE"],args["OWNER"],path)))
