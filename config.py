"""Runtime configuration, read from environment (``.env`` supported via python-dotenv).

Values are read at import so tools work out of the box, but ``FacebookAPI`` also
accepts explicit overrides in its constructor (dependency injection) so tests never
need real credentials or network access.
"""
import json
import os

try:  # python-dotenv is a convenience for local .env; not required to import config.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

# ── Facebook Graph API ────────────────────────────────────────────────────────
GRAPH_API_VERSION = os.getenv("FACEBOOK_GRAPH_API_VERSION", "v25.0")
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


# ── multi-account (multi-Page) support ────────────────────────────────────────
# The server can drive more than one Facebook Page. Accounts are resolved from an
# optional JSON file (``FACEBOOK_ACCOUNTS_FILE``) and/or the legacy single-Page env
# vars, which are always exposed as an account so the existing setup keeps working.


def default_account() -> str:
    """The account key used when a tool is called without an explicit ``account``.

    Resolution order:
    1. ``FACEBOOK_DEFAULT_ACCOUNT`` env var, if set.
    2. the sole configured account key, if exactly one exists.
    3. the literal ``"default"``.
    """
    explicit = os.getenv("FACEBOOK_DEFAULT_ACCOUNT")
    if explicit:
        return explicit
    accounts = load_accounts()
    if len(accounts) == 1:
        return next(iter(accounts))
    return "default"


def load_accounts() -> dict[str, dict]:
    """Map ``account_key -> {page_id, access_token, graph_api_version}``.

    Sources (merged; the legacy env account is added on top of the file so an
    operator can keep their current single-Page setup while adding more Pages):

    * ``FACEBOOK_ACCOUNTS_FILE`` — path to a JSON file whose top level is an object
      of ``account_key -> {"page_id", "access_token", "graph_api_version"?}``. The
      ``graph_api_version`` is optional and defaults to ``FACEBOOK_GRAPH_API_VERSION``
      (``GRAPH_API_VERSION``).
    * legacy ``FACEBOOK_ACCESS_TOKEN`` + ``FACEBOOK_PAGE_ID`` — when both are set,
      exposed under the key from ``FACEBOOK_DEFAULT_ACCOUNT`` (default ``"default"``).

    Token material is never logged. An empty map is a valid result (callers raise a
    clear error only when asked to use an absent account).
    """
    accounts: dict[str, dict] = {}

    accounts_file = os.getenv("FACEBOOK_ACCOUNTS_FILE")
    if accounts_file and os.path.isfile(accounts_file):
        with open(accounts_file, encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            raise ValueError(
                "FACEBOOK_ACCOUNTS_FILE must contain a JSON object of "
                "account_key -> {page_id, access_token, graph_api_version?}")
        for key, entry in raw.items():
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Account '{key}' in FACEBOOK_ACCOUNTS_FILE must be an object")
            accounts[key] = {
                "page_id": entry.get("page_id"),
                "access_token": entry.get("access_token"),
                "graph_api_version": entry.get("graph_api_version")
                or GRAPH_API_VERSION,
            }

    # Legacy single-env account (back-compat). Added last so it is always present
    # when configured, even alongside an accounts file.
    if PAGE_ACCESS_TOKEN and PAGE_ID:
        legacy_key = os.getenv("FACEBOOK_DEFAULT_ACCOUNT") or "default"
        accounts.setdefault(legacy_key, {
            "page_id": PAGE_ID,
            "access_token": PAGE_ACCESS_TOKEN,
            "graph_api_version": GRAPH_API_VERSION,
        })

    return accounts
