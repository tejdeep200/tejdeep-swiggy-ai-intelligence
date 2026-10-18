"""Create an encrypted RSA key pair for local dbt-to-Snowflake authentication."""

from base64 import b64encode
from getpass import getpass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


key_directory = Path.home() / ".dbt" / "keys"
private_key_file = key_directory / "swiggy_dbt_key.p8"
public_key_pem_file = key_directory / "swiggy_dbt_key_public.pem"
snowflake_public_key_file = key_directory / "swiggy_dbt_snowflake_public_key.txt"

if any(path.exists() for path in (private_key_file, public_key_pem_file, snowflake_public_key_file)):
    raise SystemExit(
        f"A dbt key already exists in {key_directory}. "
        "Do not overwrite it; rename or remove it only if you intentionally rotate the key."
    )

passphrase = getpass("Create a passphrase for the dbt private key: ")
confirmation = getpass("Confirm the passphrase: ")

if not passphrase:
    raise SystemExit("The passphrase cannot be empty.")
if passphrase != confirmation:
    raise SystemExit("The passphrases did not match. No key was created.")

key_directory.mkdir(parents=True, exist_ok=True)
private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

private_key_file.write_bytes(
    private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(passphrase.encode()),
    )
)

public_key = private_key.public_key()
public_key_pem_file.write_bytes(
    public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
)

snowflake_public_key_file.write_text(
    b64encode(
        public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    ).decode(),
    encoding="ascii",
)

print(f"Encrypted private key: {private_key_file}")
print(f"Public-key PEM: {public_key_pem_file}")
print(f"Snowflake public-key value: {snowflake_public_key_file}")
print("Keep the private key and passphrase private. The Snowflake public-key value is safe to register.")
