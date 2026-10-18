# Shared task implementation

The DAG imports the existing repository package `swiggy_platform`, mounted at
`/opt/airflow/project`. This avoids duplicate implementations:

| Responsibility | Implementation |
|---|---|
| ingestion | `airflow/dags/swiggy_load_raw.py`, `pipeline.check_stage`, `validate_files` |
| snowflake | `swiggy_platform/config.py`, RAW merge loader |
| dbt | existing `swiggy_dbt`, DAG BashOperator steps in isolated dbt venv |
| ai_enrichment | `pipeline.identify`, `enrich`, `write_enrichment` |
| embeddings | `pipeline.generate_embeddings` |
| vector_sync | `pipeline.upsert_vectors`, `validate_index` |
| data_quality | `pipeline.validate_raw`, `create_snapshot`, `validate_index` |

`../README.md` describes the legacy batch DAG. The root README describes the
new end-to-end DAG, its bounded sample and current run commands.
