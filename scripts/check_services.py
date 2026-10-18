"""Read-only checks; never print credentials or provider exception payloads."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swiggy_platform.config import load_env, connect, groq_client

load_env()
for name, check in (
    ("Groq", lambda: len(groq_client().models.list().data)),
    ("Snowflake", lambda: connect().cursor().execute("SELECT CURRENT_VERSION()").fetchone()[0]),
):
    try:
        print(f"{name}: OK ({check()})")
    except Exception as exc:
        print(f"{name}: BLOCKED ({type(exc).__name__}, code={getattr(exc, 'status_code', getattr(exc, 'errno', None))})")
