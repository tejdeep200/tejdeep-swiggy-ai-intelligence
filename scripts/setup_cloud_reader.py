"""Provision a read-only app role for the currently published immutable schemas."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swiggy_platform.config import load_env, query, database, identifier
import os

load_env()
db = database()
query("CREATE ROLE IF NOT EXISTS SWIGGY_APP_READER")
query(f"GRANT USAGE ON WAREHOUSE {identifier(os.getenv('SNOWFLAKE_WAREHOUSE', 'SWIGGY_WH'))} TO ROLE SWIGGY_APP_READER")
query(f"GRANT USAGE ON DATABASE {db} TO ROLE SWIGGY_APP_READER")
query(f"GRANT USAGE ON SCHEMA {db}.AI TO ROLE SWIGGY_APP_READER")
for table in ("PUBLICATIONS", "RAG_VECTORS"):
    query(f"GRANT SELECT ON TABLE {db}.AI.{table} TO ROLE SWIGGY_APP_READER")
for row in query(f"SHOW SCHEMAS LIKE 'SNAP_%' IN DATABASE {db}"):
    schema = identifier(row["name"])
    query(f"GRANT USAGE ON SCHEMA {db}.{schema} TO ROLE SWIGGY_APP_READER")
    query(f"GRANT SELECT ON ALL TABLES IN SCHEMA {db}.{schema} TO ROLE SWIGGY_APP_READER")
user = query("SELECT CURRENT_USER() u")[0]["u"].replace('"', '""')
query(f'GRANT ROLE SWIGGY_APP_READER TO USER "{user}"')
env_file = ROOT / "airflow/.env"
text = env_file.read_text(encoding="utf-8")
if "PUBLIC_READER_ROLE=" not in text:
    env_file.write_text(text.rstrip() + "\nPUBLIC_READER_ROLE=SWIGGY_APP_READER\n", encoding="utf-8")
print("Provisioned read-only cloud role; future pipeline snapshots grant it read access.")
