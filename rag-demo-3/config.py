"""Connection settings, all from the environment. Nothing secret is committed.

Get the real values on the VM with:

    cd azure-services/infra
    terraform output mysql_host
    terraform output -json mongo_urls     # contains the Cosmos key -- treat as secret

Both stores are PRIVATE (Cosmos has public_network_access_enabled = false, MySQL
is VNet-integrated on a delegated subnet). They are only reachable from inside
workstation-vnet -- i.e. from the RHEL VM, not from a laptop.
"""
import os

# ---- Ollama -------------------------------------------------------------
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "llama3.2:3b")

# ---- MySQL (catalogue: products, live stock) ----------------------------
MYSQL_HOST = os.environ.get("MYSQL_HOST", "")
MYSQL_USER = os.environ.get("MYSQL_USER", "roboshopadmin")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "catalogue")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))

# Azure MySQL Flexible Server requires TLS. The server presents a DigiCert
# chain, which is already in the RHEL system trust store -- so the default CA
# bundle works and no extra download is needed. Override MYSQL_SSL_CA if your
# box keeps it elsewhere, or set MYSQL_TLS=false for a local plaintext MySQL.
MYSQL_TLS = os.environ.get("MYSQL_TLS", "true").lower() not in ("false", "0", "no")
MYSQL_SSL_CA = os.environ.get("MYSQL_SSL_CA", "/etc/pki/tls/certs/ca-bundle.crt")

# ---- MongoDB / Cosmos (orders: the sale data) ---------------------------
# terraform output -json mongo_urls  ->  .orders
MONGO_URL = os.environ.get("MONGO_URL", "")
MONGO_DB = os.environ.get("MONGO_DB", "orders")
MONGO_COLLECTION = os.environ.get("MONGO_COLLECTION", "orders")

# Cosmos can be slow to hand out a first connection; fail fast rather than hang.
MONGO_TIMEOUT_MS = int(os.environ.get("MONGO_TIMEOUT_MS", "8000"))


def missing(*names):
    """Return the names among `names` that have no value set."""
    return [n for n in names if not globals().get(n)]


def require(*names):
    """Exit with an actionable message if any required setting is unset."""
    gaps = missing(*names)
    if gaps:
        raise SystemExit(
            "missing required environment variable(s): " + ", ".join(gaps) + "\n\n"
            "Set them from the Terraform outputs, e.g.:\n"
            "  export MYSQL_HOST=$(cd ../../azure-services/infra && terraform output -raw mysql_host)\n"
            "  export MYSQL_PASSWORD='RoboShop@1'\n"
            "  export MONGO_URL=$(cd ../../azure-services/infra && "
            "terraform output -json mongo_urls | python3 -c "
            "'import json,sys; print(json.load(sys.stdin)[\"orders\"])')"
        )


def summary():
    """Human-readable, secret-free view of where we are pointed."""
    host = MYSQL_HOST or "(unset)"
    mongo = "(unset)"
    if MONGO_URL:
        # Never print the connection string: it embeds the Cosmos primary key.
        tail = MONGO_URL.split("@")[-1].split("/")[0] if "@" in MONGO_URL else "?"
        mongo = f"{tail} db={MONGO_DB} coll={MONGO_COLLECTION}"
    return (f"mysql: {MYSQL_USER}@{host}:{MYSQL_PORT}/{MYSQL_DATABASE} "
            f"tls={'on' if MYSQL_TLS else 'off'}\nmongo: {mongo}")
