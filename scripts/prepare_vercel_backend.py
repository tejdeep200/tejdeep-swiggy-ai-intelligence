"""Stage only server code; private keys are supplied separately as platform secrets."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
destination = ROOT / "runtime/vercel-backend"
destination.mkdir(parents=True, exist_ok=True)
for directory in ("backend", "swiggy_platform", "config"):
    shutil.copytree(ROOT / directory, destination / directory, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "requirements.txt", "Dockerfile"))
for source in (ROOT / "deploy/vercel-backend").iterdir():
    shutil.copy2(source, destination / source.name)
print("Prepared credential-free backend source in runtime/vercel-backend")
