# Swiggy Airflow locally

The Zomato reference was adapted to Swiggy. The DAG loads cities, cuisines,
restaurants, and restaurant_cuisines from the existing internal Snowflake stage,
then runs dbt deps and dbt build (models, tests, and snapshots). There is no review
AI task because this project has no review dataset or enrichment script.

1. Start Docker Desktop with the Linux container engine.
2. From the workspace root run `.venv\Scripts\python.exe scripts\setup_airflow.py` once.
3. Edit `airflow/.env` privately: enter the encrypted key passphrase and verify the account,
   username, role and key directory. The encrypted key stays outside the repository.
4. Run `cd airflow`, then `docker compose config --quiet`, then `docker compose up -d --build`.
5. Open http://localhost:8081. Username: `admin`; password: `AIRFLOW_ADMIN_PASSWORD` in `airflow/.env`.
6. Check `docker compose exec scheduler airflow dags list-import-errors`.
7. Unpause `swiggy_batch` to enable daily runs (UTC), or trigger a manual run once enabled.

The host dbt installation is unchanged. Docker uses dbt-snowflake and dbt-core 1.10.x in its
own environment. The image builds and the DAG imports successfully.
The profile uses Linux key paths and the existing swiggy_dbt profile name.

The existing RAW tables and SWIGGY.RAW.CSV_FMT must already exist. The loader
copies files from SWIGGY_LOCAL_STAGE into fresh temporary tables, then merges
into RAW by CITY_ID, CUISINE_ID, LISTING_ID, or the listing/cuisine pair.
It removes exact duplicates from the input and rejects null keys, conflicting
versions of the same key, and existing duplicate target keys. COPY FORCE applies
only to temporary tables. Retries do not append existing rows. Missing source
keys are not deleted. Keep one current version per key across staged files;
conflicting historical versions require a separate batch/version policy.
Set SWIGGY_RAW_STAGE to the verified Azure stage if needed.
This DAG does not upload local CSV files or provision Snowflake/cloud resources.

Use `docker compose ps` and `docker compose logs --tail 100` for diagnosis.
Stop with `docker compose down`; omit `--volumes` to retain metadata.
This setup is for local development. The UI binds only to localhost. Rotating the
admin password in .env after initialization also requires resetting the Airflow user.

Reference for the Airflow 3 services and execution API configuration: https://airflow.apache.org/docs/apache-airflow/3.0.3/howto/docker-compose/index.html

Container dbt writes generated artifacts to /tmp/swiggy_dbt_target to avoid collisions with the workstation dbt version in swiggy_dbt/target. The verified RAW duplicate repair has backups under SWIGGY.RAW.<table>_AIRFLOW_BACKUP_20261017.
