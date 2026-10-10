"""Render ASL with account-specific config: output stays in ignored .runtime."""
import argparse
import json
from pathlib import Path


def build(c):
    def glue(job, extra):
        args = {"--BUCKET":c["bucket"], "--BATCH_ID.$":"$.batch_id", "--ATTEMPT_ID.$":"$.attempt_id", "--UPPER_UTC.$":"$.upper_utc", **extra}
        return {"Type":"Task", "Resource":"arn:aws:states:::glue:startJobRun.sync", "Parameters":{"JobName":job,"Arguments":args},
                "ResultPath":None, "TimeoutSeconds":1800, "Catch":[{"ErrorEquals":["States.ALL"],"ResultPath":"$.failure","Next":"FailedLockRetained"}]}
    states = {
        "Acquire": {"Type":"Task","Resource":"arn:aws:states:::lambda:invoke",
            "Parameters":{"FunctionName":c["lock_function"],"Payload":{"action":"acquire","owner.$":"$$.Execution.Id"}},"ResultPath":None,"Next":"Extract"},
        "Extract":glue(c["extract_job"],{"--PG_CONNECTION":c["pg_connection"],"--MONGO_CONNECTION":c["mongo_connection"]}),
        "Validate":{"Type":"Task","Resource":"arn:aws:states:::lambda:invoke","Parameters":{"FunctionName":c["validate_function"],"Payload.$":"$"},"ResultPath":None,"Next":"Transform",
            "Catch":[{"ErrorEquals":["States.ALL"],"ResultPath":"$.failure","Next":"FailedLockRetained"}]},
        "Transform":glue(c["transform_job"],{}),
        "Publish":glue(c["publish_job"],{"--SNOWFLAKE_SECRET":c["snowflake_secret"],"--LOCK_TABLE":c["lock_table"],"--OWNER.$":"$$.Execution.Id","--PUBLISH_SQL_KEY":c["publish_sql_key"]}),
        "Release":{"Type":"Task","Resource":"arn:aws:states:::lambda:invoke","Parameters":{"FunctionName":c["lock_function"],"Payload":{"action":"release","owner.$":"$$.Execution.Id"}},"ResultPath":None,"End":True},
        "FailedLockRetained":{"Type":"Fail","Error":"PipelineFailedLockRetained","Cause":"Reconcile running jobs and Snowflake ledger/queries before manually releasing lock."},
    }
    for a,b in [("Extract","Validate"),("Transform","Publish"),("Publish","Release")]:
        states[a]["Next"] = b
    return {"Comment":"Bounded snapshot teaching workflow; failed execution retains durable lock. No blind automatic retries.","StartAt":"Acquire","TimeoutSeconds":7200,"States":states}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config/cloud.example.json")
    p.add_argument("--out", default=".runtime/state-machine.json")
    a = p.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(build(json.loads(Path(a.config).read_text())),indent=2)+"\n")
    print(out)
