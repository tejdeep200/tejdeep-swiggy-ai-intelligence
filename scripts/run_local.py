"""Start the API and Next.js together without putting secrets in frontend files."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swiggy_platform.config import load_env


def main():
    load_env()
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT)
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    frontend = subprocess.Popen([npm, "run", "start", "--", "--hostname", "127.0.0.1"], cwd=ROOT / "frontend")
    print("Website: http://localhost:3000 | API: http://localhost:8000", flush=True)
    try:
        while True:
            if api.poll() is not None or frontend.poll() is not None:
                raise RuntimeError("A local service exited; inspect its output")
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        api.terminate()
        frontend.terminate()


if __name__ == "__main__":
    main()
