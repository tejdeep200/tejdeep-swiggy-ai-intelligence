"""Send deployment secrets over stdin; never write them into deployment source."""
import argparse
import base64
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swiggy_platform.config import load_env

parser = argparse.ArgumentParser()
parser.add_argument("target", choices=["backend", "frontend", "voice"])
parser.add_argument("--backend-url")
parser.add_argument("--speech-url")
args = parser.parse_args()
load_env()
if args.target == "backend":
    directory = ROOT / "runtime/vercel-backend"
    names = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "DBT_SNOWFLAKE_KEY_PASSPHRASE", "GROQ_API_KEY", "GROQ_MODEL", "APP_API_TOKEN")
    values = {name: os.environ[name] for name in names}
    key = Path(os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH", str(Path(os.environ["SNOWFLAKE_KEY_DIR"]) / "swiggy_dbt_key.p8")))
    values.update(SNOWFLAKE_PRIVATE_KEY_BASE64=base64.b64encode(key.read_bytes()).decode(),
                  SNOWFLAKE_ROLE="SWIGGY_APP_READER", SNOWFLAKE_DATABASE="SWIGGY", SNOWFLAKE_WAREHOUSE="SWIGGY_WH",
                  RAG_STORE="snowflake", GROQ_MODEL=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"))
elif args.target == "voice":
    directory = ROOT / "runtime/vercel-voice"
    values = {name: os.environ[name] for name in ("GROQ_API_KEY", "APP_API_TOKEN")}
else:
    if not args.backend_url:
        parser.error("--backend-url is required")
    directory = ROOT / "frontend"
    values = {"BACKEND_URL": args.backend_url, "APP_API_TOKEN": os.environ["APP_API_TOKEN"]}
    if args.speech_url:
        values["SPEECH_URL"] = args.speech_url

for name, value in values.items():
    completed = subprocess.run(["npx.cmd" if os.name == "nt" else "npx", "--yes", "vercel", "env", "add", name,
                                "production", "--sensitive", "--force", "--yes", "--cwd", str(directory)],
                               input=value, text=True, capture_output=True)
    if completed.returncode:
        raise SystemExit(f"Could not configure {name}; CLI exit code {completed.returncode}")
    print(f"Configured {name}", flush=True)
