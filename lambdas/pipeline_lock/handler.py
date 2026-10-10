"""Non-expiring demo mutex. A failed workflow intentionally leaves it held.

No automatic TTL takeover: a timed-out Snowflake query may still be running.
Recovery requires query/job reconciliation before an operator removes the lock.
"""
import os


def handler(event, context):
    import boto3
    table = boto3.resource("dynamodb").Table(os.environ["LOCK_TABLE"])
    owner = event["owner"]
    key = {"pipeline_id": "ecommerce"}
    if event["action"] == "acquire":
        table.put_item(Item={**key, "owner":owner}, ConditionExpression="attribute_not_exists(pipeline_id)")
    elif event["action"] == "release":
        table.delete_item(Key=key, ConditionExpression="#o=:owner", ExpressionAttributeNames={"#o":"owner"}, ExpressionAttributeValues={":owner":owner})
    else:
        raise ValueError("Unknown lock action")
    return {"owner":owner}
