"""Publish validated immutable data for the independent conversational API."""
import os
from datetime import datetime, timedelta, timezone

from airflow.sdk import DAG, task, get_current_context
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.empty import EmptyOperator
from swiggy_platform.pipeline import failure_notification

DBT = "/opt/airflow/dbt_venv/bin/dbt"
ARGS = "--project-dir /opt/airflow/dbt/swiggy_dbt --profiles-dir /opt/airflow/dbt/profiles --target-path /tmp/swiggy_ai_target"

with DAG(
    "swiggy_ai_end_to_end_pipeline", start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    schedule=os.getenv("SWIGGY_SCHEDULE", "@daily") or None, catchup=False, max_active_runs=1,
    default_args={"retries": 3, "retry_delay": timedelta(minutes=1), "retry_exponential_backoff": True,
                  "max_retry_delay": timedelta(minutes=15), "execution_timeout": timedelta(hours=2),
                  "on_failure_callback": failure_notification},
    tags=["swiggy", "ai", "publication"],
) as dag:
    start = EmptyOperator(task_id="start")

    @task
    def check_aws_s3_files():
        from swiggy_platform.pipeline import check_stage
        return check_stage(os.getenv("SWIGGY_S3_STAGE", ""))

    @task
    def check_azure_adls_files():
        from swiggy_platform.pipeline import check_stage
        return check_stage(os.getenv("SWIGGY_ADLS_STAGE", ""))

    @task
    def validate_source_files(s3, azure):
        from swiggy_platform.pipeline import check_stage, validate_files
        # Reuse the verified internal stage until external integrations are ready.
        sources = [s3, azure]
        if not any(s["configured"] for s in sources):
            sources.append(check_stage(os.getenv("SWIGGY_RAW_STAGE", "SWIGGY.RAW.SWIGGY_LOCAL_STAGE")))
        return validate_files(sources)

    s3, azure = check_aws_s3_files(), check_azure_adls_files()
    start >> [s3, azure]
    files = validate_source_files(s3, azure)
    load = BashOperator(task_id="load_raw_data_into_snowflake", bash_command="/opt/airflow/dbt_venv/bin/python /opt/airflow/dags/swiggy_load_raw.py")

    @task
    def validate_raw_tables():
        from swiggy_platform.pipeline import validate_raw
        validate_raw()

    raw = validate_raw_tables()
    files >> load >> raw
    deps = BashOperator(task_id="dbt_dependencies", bash_command=f"{DBT} deps --project-dir /opt/airflow/dbt/swiggy_dbt --profiles-dir /opt/airflow/dbt/profiles")
    staging = BashOperator(task_id="execute_dbt_staging_models", bash_command=f"{DBT} run {ARGS} --select path:models/staging")
    # No intermediate models exist in this repository. A named pass-through keeps
    # that fact visible without fabricating a second transformation project.
    intermediate = EmptyOperator(task_id="intermediate_models_not_present")
    marts = BashOperator(task_id="execute_dbt_mart_models", bash_command=f"{DBT} run {ARGS} --select path:models/marts")
    history = BashOperator(task_id="preserve_dbt_snapshots", bash_command=f"{DBT} snapshot {ARGS}")
    tests = BashOperator(task_id="run_dbt_tests", bash_command=f"{DBT} test {ARGS}")
    raw >> deps >> staging >> intermediate >> marts >> history >> tests

    @task
    def check_data_quality_and_freshness():
        from swiggy_platform.pipeline import create_snapshot
        return create_snapshot(get_current_context()["run_id"])

    @task
    def identify_new_updated_records(snapshot):
        from swiggy_platform.pipeline import identify
        return identify(snapshot)

    @task(pool="groq_api", max_active_tis_per_dag=1)
    def groq_llm_ai_enrichment(snapshot):
        from swiggy_platform.pipeline import enrich
        return enrich(snapshot)

    @task
    def write_ai_columns_to_snowflake(snapshot):
        from swiggy_platform.pipeline import write_enrichment
        return write_enrichment(snapshot)

    @task(pool="embedding_workers")
    def generate_hugging_face_embeddings(snapshot):
        from swiggy_platform.pipeline import generate_embeddings
        return generate_embeddings(snapshot)

    @task
    def upsert_documents_into_chromadb(snapshot):
        from swiggy_platform.pipeline import upsert_vectors
        return upsert_vectors(snapshot)

    @task
    def validate_rag_index_and_row_counts(snapshot):
        from swiggy_platform.pipeline import validate_index
        return validate_index(snapshot)

    @task
    def optional_powerbi_refresh(snapshot):
        from swiggy_platform.powerbi import refresh_all
        return refresh_all()

    @task
    def publish_analytics_ready_status(snapshot, powerbi):
        from swiggy_platform.pipeline import publish
        publish(snapshot, get_current_context()["run_id"], powerbi)

    quality = check_data_quality_and_freshness()
    tests >> quality
    changed = identify_new_updated_records(quality)
    ai = groq_llm_ai_enrichment(changed)
    written = write_ai_columns_to_snowflake(ai)
    embeddings = generate_hugging_face_embeddings(written)
    vectors = upsert_documents_into_chromadb(embeddings)
    validated = validate_rag_index_and_row_counts(vectors)
    powerbi = optional_powerbi_refresh(validated)
    published = publish_analytics_ready_status(validated, powerbi)
    published >> EmptyOperator(task_id="success_and_monitoring")
