"""Create local Airflow secrets without overwriting an existing .env."""
import base64
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "airflow"
text = (root.parent / ".env.example").read_text(encoding="utf-8")
text = text.replace("APP_API_TOKEN=\n", "APP_API_TOKEN=" + secrets.token_urlsafe(32) + "\n")
text = text.replace("AIRFLOW_JWT_SECRET=\n", "AIRFLOW_JWT_SECRET=" + secrets.token_hex(32) + "\n")
text = text.replace("AIRFLOW_FERNET_KEY=\n", "AIRFLOW_FERNET_KEY=" + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode() + "\n")
text = text.replace("AIRFLOW_ADMIN_PASSWORD=\n", "AIRFLOW_ADMIN_PASSWORD=" + secrets.token_urlsafe(24) + "\n")
try:
    with (root / ".env").open("x", encoding="utf-8") as destination:
        destination.write(text)
except FileExistsError:
    raise SystemExit(".env already exists; left unchanged.")
print("Created .env. Enter the key passphrase there privately. Admin password is in AIRFLOW_ADMIN_PASSWORD.")
