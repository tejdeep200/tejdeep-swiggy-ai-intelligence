"""Stage voice separately so model caches cannot crowd analytics storage."""
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "runtime/vercel-voice"
target.mkdir(parents=True, exist_ok=True)
for source in (ROOT / "deploy/vercel-voice").iterdir():
    shutil.copy2(source, target / source.name)
package = target / "swiggy_platform"
package.mkdir(exist_ok=True)
for name in ("__init__.py", "speech.py", "config.py"):
    shutil.copy2(ROOT / "swiggy_platform" / name, package / name)
print("Prepared credential-free voice source")
