FROM apache/airflow:3.0.3-python3.12
# Match providers to the Airflow release instead of upgrading Airflow implicitly.
RUN pip install --no-cache-dir "apache-airflow==3.0.3" \
    apache-airflow-providers-fab apache-airflow-providers-standard \
    apache-airflow-providers-snowflake apache-airflow-providers-amazon \
    apache-airflow-providers-microsoft-azure \
    --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.0.3/constraints-3.12.txt
# Separate dbt environment prevents dependency conflicts with Airflow.
RUN python -m venv /opt/airflow/dbt_venv && \
    /opt/airflow/dbt_venv/bin/pip install --no-cache-dir "dbt-snowflake>=1.10,<1.11" "dbt-core>=1.10,<1.11"
COPY requirements.txt /tmp/swiggy-requirements.txt
RUN pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir "apache-airflow==3.0.3" -r /tmp/swiggy-requirements.txt
