"""Load Swiggy CSVs from the existing internal stage, then build and test dbt."""
from datetime import datetime, timedelta, timezone
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

DBT = "/opt/airflow/dbt_venv/bin/dbt"
PROJECT = "/opt/airflow/dbt/swiggy_dbt"
PROFILES = "/opt/airflow/dbt/profiles"

with DAG(
    dag_id="swiggy_batch",
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["swiggy", "dbt", "snowflake"],
    doc_md=__doc__,
) as dag:
    reload_raw = BashOperator(
        task_id="reload_raw",
        # Run in the isolated dbt environment, which includes the Snowflake connector.
        bash_command="/opt/airflow/dbt_venv/bin/python /opt/airflow/dags/swiggy_load_raw.py",
        execution_timeout=timedelta(minutes=20),
    )
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"{DBT} deps --project-dir {PROJECT} --profiles-dir {PROFILES} && "
                     f"{DBT} build --project-dir {PROJECT} --profiles-dir {PROFILES} --target-path /tmp/swiggy_dbt_target",
        execution_timeout=timedelta(minutes=30),
    )
    reload_raw >> dbt_build
