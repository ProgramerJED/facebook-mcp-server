"""Runtime configuration, read from environment (``.env`` supported via python-dotenv).

Values are read at import so tools work out of the box, but ``FacebookAPI`` also
accepts explicit overrides in its constructor (dependency injection) so tests never
need real credentials or network access.
"""
import os

try:  # python-dotenv is a convenience for local .env; not required to import config.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

# ── Facebook Graph API ────────────────────────────────────────────────────────
GRAPH_API_VERSION = os.getenv("FACEBOOK_GRAPH_API_VERSION", "v22.0")
PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
GRAPH_API_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# ── request hardening ─────────────────────────────────────────────────────────
# Bound every call so a hung connection can never wedge the MCP process.
REQUEST_TIMEOUT_SECONDS = float(os.getenv("FACEBOOK_REQUEST_TIMEOUT_SECONDS", "15"))
# Bounded retry for rate-limit / transient Graph API errors (0 disables).
MAX_RETRIES = int(os.getenv("FACEBOOK_MAX_RETRIES", "2"))


def missing_credentials() -> list[str]:
    """Names of the required env vars that are not set (empty list = configured)."""
    return [
        name
        for name, value in (
            ("FACEBOOK_ACCESS_TOKEN", PAGE_ACCESS_TOKEN),
            ("FACEBOOK_PAGE_ID", PAGE_ID),
        )
        if not value
    ]
