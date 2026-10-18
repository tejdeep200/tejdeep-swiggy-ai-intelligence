import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env():
    from dotenv import load_dotenv
    load_dotenv(ROOT / "airflow" / ".env", override=False)


def identifier(value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError("Invalid SQL identifier")
    return value.upper()


def database():
    return identifier(os.getenv("SNOWFLAKE_DATABASE", "SWIGGY"))


def connect():
    # Explicit credentials are supplied below; use an isolated writable connector
    # config directory rather than unrelated workstation connections.toml files.
    import tempfile
    config_dir = Path(tempfile.gettempdir()) / "swiggy_snowflake_config"
    config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("SNOWFLAKE_HOME", str(config_dir))
    import snowflake.connector
    kwargs = dict(account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
                  role=os.getenv("SNOWFLAKE_ROLE", "DBT_ROLE"),
                  warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "SWIGGY_WH"),
                  database=database(), schema="MARTS", login_timeout=30,
                  session_parameters={"STATEMENT_TIMEOUT_IN_SECONDS": 120, "QUERY_TAG": "swiggy_ai"})
    key = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    if not key:
        key = str(Path(os.getenv("SNOWFLAKE_KEY_DIR", str(Path.home() / ".dbt/keys"))) / "swiggy_dbt_key.p8")
    kwargs.update(private_key_file=key, private_key_file_pwd=os.environ["DBT_SNOWFLAKE_KEY_PASSPHRASE"])
    return snowflake.connector.connect(**kwargs)


def query(sql, params=None):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(sql, params)
        if cursor.description is None:
            return []
        columns = [c[0].lower() for c in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def execute_many(sql, rows):
    with connect() as connection, connection.cursor() as cursor:
        cursor.executemany(sql, rows)


def groq_client():
    from groq import Groq
    return Groq(api_key=os.environ["GROQ_API_KEY"], max_retries=6, timeout=60)


def llm(messages, json_mode=False):
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    if "gpt-oss" in model:
        kwargs["reasoning_effort"] = "low"
    return groq_client().chat.completions.create(
        model=model,
        messages=messages, temperature=0, max_tokens=2500, **kwargs,
    ).choices[0].message.content
