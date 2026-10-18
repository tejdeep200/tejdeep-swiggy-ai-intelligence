"""Build a source-only archive and reject known local secrets before upload."""
from pathlib import Path
import json
import os
import re
import zipfile

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("frontend", "backend", "swiggy_platform", "config", "airflow", "swiggy_dbt", "scripts", "deploy")
EXCLUDED = {"node_modules", ".next", ".vercel", "__pycache__", "logs", "target", "dbt_packages", ".pytest_cache"}
ROOT_FILES = ("README.md", ".gitignore", ".dockerignore", ".env.example", "docker-compose.yml", "requirements.txt")
EXTENSIONS = {".py", ".sql", ".yml", ".yaml", ".md", ".json", ".toml", ".mjs", ".ts", ".tsx", ".css", ".txt"}


def prepare():
    files = [ROOT / name for name in ROOT_FILES]
    for directory in SOURCE_DIRS:
        for parent, directories, names in os.walk(ROOT / directory):
            directories[:] = [name for name in directories if name not in EXCLUDED]
            for name in names:
                path = Path(parent) / name
                if name.startswith(".env") or name == "example.env":
                    continue
                if path.suffix in EXTENSIONS or name in {"Dockerfile", ".dockerignore", ".gitignore"}:
                    files.append(path)
    values = dotenv_values(ROOT / "airflow/.env")
    secret_values = [value for key, value in values.items() if value and len(value) >= 12 and
                     any(word in key for word in ("SECRET", "PASSWORD", "PASSPHRASE", "TOKEN", "API_KEY", "FERNET"))]
    for path in files:
        text = path.read_text(encoding="utf-8-sig")
        if any(value in text for value in secret_values) or re.search(
            r"gsk_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |ENCRYPTED )?PRIVATE KEY-----", text
        ):
            raise ValueError("Potential secret found; upload blocked: " + str(path.relative_to(ROOT)))
    destination = ROOT / "runtime" / "swiggy-ai-source.zip"
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            archive.write(path, path.relative_to(ROOT).as_posix())
    manifest = {"file_count": len(set(files)), "archive": str(destination), "bytes": destination.stat().st_size,
                "secret_scan": "passed", "files": sorted(p.relative_to(ROOT).as_posix() for p in set(files))}
    (destination.parent / "github-export-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({key: value for key, value in manifest.items() if key != "files"}))


if __name__ == "__main__":
    prepare()
