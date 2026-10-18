"""Publish an explicitly curated-only baseline after the existing dbt tests pass.

This does not claim that enrichment or RAG is complete. The full Airflow DAG
replaces it only after all its checkpoints pass.
"""
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swiggy_platform.config import load_env
from swiggy_platform.pipeline import create_snapshot, publish


def main():
    load_env()
    import tempfile
    config_dir = Path(tempfile.gettempdir()) / "swiggy_snowflake_config"
    config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("SNOWFLAKE_HOME", str(config_dir))
    os.environ.setdefault("SNOWFLAKE_PRIVATE_KEY_PATH", str(
        Path(os.getenv("SNOWFLAKE_KEY_DIR", str(Path.home() / ".dbt/keys"))) / "swiggy_dbt_key.p8"))
    profiles = ROOT / "runtime" / "profiles"
    profiles.mkdir(parents=True, exist_ok=True)
    # This profile contains env references, never secret values.
    text = (ROOT / "airflow/profiles/profiles.yml").read_text()
    text = text.replace("/opt/airflow/keys/swiggy_dbt_key.p8", '"{{ env_var(\'SNOWFLAKE_PRIVATE_KEY_PATH\') }}"')
    (profiles / "profiles.yml").write_text(text)
    dbt = Path(sys.executable).parent / ("dbt.exe" if os.name == "nt" else "dbt")
    subprocess.run([str(dbt), "test", "--project-dir", str(ROOT / "swiggy_dbt"),
                    "--profiles-dir", str(profiles), "--target-path", str(ROOT / "runtime/dbt_target")], check=True)
    run_id = "curated_baseline_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot = create_snapshot(run_id)
    publish(snapshot, run_id, [], ai_ready=False, rag_ready=False)
    print(f"Published {snapshot['rows']} validated listings. AI enrichment and RAG are pending.")


if __name__ == "__main__":
    main()
