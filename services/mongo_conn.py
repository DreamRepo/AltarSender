from pymongo import MongoClient
from pymongo.errors import ConfigurationError
import urllib.parse

DEFAULT_TIMEOUT_MS = 4000

class ClientWithAddress(MongoClient):
    """Small wrapper to keep a masked URI available for display."""
    def __init__(self, *args, address_string: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.address_string = address_string

def _build_uri(host: str, port: str, user: str, pwd: str, db: str) -> str:
    host = host or "localhost"
    port = port or "27017"
    db   = db or "admin"
    auth = ""
    if user and pwd:
        auth = f"{urllib.parse.quote_plus(user)}:{urllib.parse.quote_plus(pwd)}@"
    return f"mongodb://{auth}{host}:{port}/{db}"

def mongo_client_from_inputs(
    use_uri: bool,
    uri: str,
    host: str,
    port: str,
    user: str,
    pwd: str,
    db: str,
    tls: bool,
) -> ClientWithAddress:
    if use_uri:
        if not uri:
            raise ConfigurationError("Empty URI.")
        client = ClientWithAddress(
            uri,
            serverSelectionTimeoutMS=DEFAULT_TIMEOUT_MS,
            address_string=uri
        )
    else:
        built_uri = _build_uri(host, port, user, pwd, db)
        client = ClientWithAddress(
            built_uri,
            tls=bool(tls),
            serverSelectionTimeoutMS=DEFAULT_TIMEOUT_MS,
            address_string=built_uri
        )
    return client

def ping_and_get_dbname(client: MongoClient) -> str:
    # ping
    client.admin.command("ping")
    # default DB name if present; otherwise "admin"
    from pymongo.errors import ConfigurationError as _CfgErr
    try:
        return client.get_database().name  # peut lever ConfigurationError si aucune DB par défaut
    except _CfgErr:
        return "admin"


# --- Helpers for building Mongo URL for observers (e.g., Sacred) ---
def build_mongo_url_from_payload(mongo_payload: dict) -> tuple[str, str]:
    """Return (mongo_url, db_name) from a UI payload.

    Supports either a full URI (with optional tls, authSource additions) or
    host/port/user/password fields. Always includes authSource to target the
    provided database for authentication.
    """
    if not isinstance(mongo_payload, dict) or not mongo_payload:
        raise ValueError("Mongo connection incorrect")

    use_uri = bool(mongo_payload.get("use_uri", 0))
    db_name = (mongo_payload.get("db") or "admin")

    if use_uri:
        mongo_url = (mongo_payload.get("uri") or "").strip()
        if not mongo_url:
            raise ValueError("Empty Mongo URI")
        # Append authSource if missing and db provided
        if "authSource=" not in mongo_url and db_name:
            sep = "&" if "?" in mongo_url else "?"
            mongo_url = f"{mongo_url}{sep}authSource={db_name}"
        # Append tls for non-SRV if requested
        if bool(mongo_payload.get("tls", 0)) and not mongo_url.startswith("mongodb+srv://") and "tls=" not in mongo_url:
            sep = "&" if "?" in mongo_url else "?"
            mongo_url = f"{mongo_url}{sep}tls=true"
        return mongo_url, db_name

    # Host/port path: build from parts and include authSource/tls
    host = (mongo_payload.get("host") or "localhost").strip()
    port = (mongo_payload.get("port") or "27017").strip()
    user = (mongo_payload.get("user") or "").strip()
    pwd = (mongo_payload.get("password") or "").strip()
    auth = f"{urllib.parse.quote_plus(user)}:{urllib.parse.quote_plus(pwd)}@" if user and pwd else ""
    params: list[str] = [f"authSource={db_name}"]
    if bool(mongo_payload.get("tls", 0)):
        params.append("tls=true")
    query = ("?" + "&".join(params)) if params else ""
    mongo_url = f"mongodb://{auth}{host}:{port}/{db_name}{query}"
    return mongo_url, db_name