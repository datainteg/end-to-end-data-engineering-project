"""Airflow 2.x candidate DAG; install a compatible Amazon provider separately."""
import os
from datetime import datetime, timezone
from airflow import DAG
from airflow.providers.amazon.aws.operators.step_function import StepFunctionStartExecutionOperator
from airflow.providers.amazon.aws.sensors.step_function import StepFunctionExecutionSensor

with DAG("ecommerce_batch", start_date=datetime(2026,1,1,tzinfo=timezone.utc), schedule=None,
         catchup=False, max_active_runs=1, default_args={"retries":0}, tags=["ecommerce","demo"]) as dag:
    start = StepFunctionStartExecutionOperator(
        task_id="start", state_machine_arn=os.environ["STATE_MACHINE_ARN"],
        state_machine_input={"batch_id":"{{ dag_run.conf['batch_id'] }}", "attempt_id":"{{ dag_run.conf['attempt_id'] }}", "upper_utc":"{{ dag_run.conf['upper_utc'] }}"},
        aws_conn_id="aws_default", do_xcom_push=True)
    wait = StepFunctionExecutionSensor(task_id="wait_for_terminal", execution_arn=start.output,
        aws_conn_id="aws_default", mode="reschedule", poke_interval=30, timeout=7500)
    start >> wait
