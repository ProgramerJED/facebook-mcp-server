"""Multi-account (multi-Page) support: config resolution + Manager routing.

Every test avoids the network — Graph API calls go through the ``stub`` fixture, and
account resolution is driven by monkeypatched env / config values. Token material must
never appear in ``list_accounts`` output or in the unknown-account error.
"""
import json

import pytest

import config
from _fakes import FakeResponse
from manager import Manager


def _clear_account_env(monkeypatch):
    """Start from a clean slate: no file, no legacy env, no explicit default."""
    monkeypatch.delenv("FACEBOOK_ACCOUNTS_FILE", raising=False)
    monkeypatch.delenv("FACEBOOK_DEFAULT_ACCOUNT", raising=False)
    # Legacy creds are read into module-level constants at import → patch those too.
    monkeypatch.setattr(config, "PAGE_ID", None)
    monkeypatch.setattr(config, "PAGE_ACCESS_TOKEN", None)


# ── config.load_accounts ─────────────────────────────────────────────────────

def test_load_accounts_parses_file(tmp_path, monkeypatch):
    _clear_account_env(monkeypatch)
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(json.dumps({
        "brand_a": {"page_id": "PAGE_A", "access_token": "TOKEN_A",
                    "graph_api_version": "v20.0"},
        "brand_b": {"page_id": "PAGE_B", "access_token": "TOKEN_B"},
    }))
    monkeypatch.setenv("FACEBOOK_ACCOUNTS_FILE", str(accounts_file))

    accounts = config.load_accounts()
    assert set(accounts) == {"brand_a", "brand_b"}
    assert accounts["brand_a"] == {
        "page_id": "PAGE_A", "access_token": "TOKEN_A",
        "graph_api_version": "v20.0"}
    # missing graph_api_version defaults to the global version
    assert accounts["brand_b"]["graph_api_version"] == config.GRAPH_API_VERSION


def test_load_accounts_legacy_single_env(monkeypatch):
    _clear_account_env(monkeypatch)
    monkeypatch.setattr(config, "PAGE_ID", "LEGACY_PAGE")
    monkeypatch.setattr(config, "PAGE_ACCESS_TOKEN", "LEGACY_TOKEN")

    accounts = config.load_accounts()
    assert list(accounts) == ["default"]
    assert accounts["default"]["page_id"] == "LEGACY_PAGE"
    assert accounts["default"]["access_token"] == "LEGACY_TOKEN"


def test_load_accounts_legacy_key_from_default_env(monkeypatch):
    _clear_account_env(monkeypatch)
    monkeypatch.setattr(config, "PAGE_ID", "LEGACY_PAGE")
    monkeypatch.setattr(config, "PAGE_ACCESS_TOKEN", "LEGACY_TOKEN")
    monkeypatch.setenv("FACEBOOK_DEFAULT_ACCOUNT", "primary")

    accounts = config.load_accounts()
    assert list(accounts) == ["primary"]


def test_load_accounts_merges_file_and_legacy(tmp_path, monkeypatch):
    _clear_account_env(monkeypatch)
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(json.dumps({
        "brand_a": {"page_id": "PAGE_A", "access_token": "TOKEN_A"},
    }))
    monkeypatch.setenv("FACEBOOK_ACCOUNTS_FILE", str(accounts_file))
    monkeypatch.setattr(config, "PAGE_ID", "LEGACY_PAGE")
    monkeypatch.setattr(config, "PAGE_ACCESS_TOKEN", "LEGACY_TOKEN")

    accounts = config.load_accounts()
    assert set(accounts) == {"brand_a", "default"}
    assert accounts["default"]["page_id"] == "LEGACY_PAGE"


def test_load_accounts_empty_when_unconfigured(monkeypatch):
    _clear_account_env(monkeypatch)
    assert config.load_accounts() == {}


# ── config.default_account ───────────────────────────────────────────────────

def test_default_account_explicit_env_wins(monkeypatch):
    _clear_account_env(monkeypatch)
    monkeypatch.setenv("FACEBOOK_DEFAULT_ACCOUNT", "chosen")
    assert config.default_account() == "chosen"


def test_default_account_sole_account(tmp_path, monkeypatch):
    _clear_account_env(monkeypatch)
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(json.dumps({
        "only_one": {"page_id": "P", "access_token": "T"}}))
    monkeypatch.setenv("FACEBOOK_ACCOUNTS_FILE", str(accounts_file))
    assert config.default_account() == "only_one"


def test_default_account_falls_back_to_literal(monkeypatch):
    _clear_account_env(monkeypatch)
    assert config.default_account() == "default"


# ── Manager._api routing ─────────────────────────────────────────────────────

def test_api_builds_client_bound_to_account(tmp_path, monkeypatch):
    _clear_account_env(monkeypatch)
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(json.dumps({
        "brand_a": {"page_id": "PAGE_A", "access_token": "TOKEN_A",
                    "graph_api_version": "v20.0"},
        "brand_b": {"page_id": "PAGE_B", "access_token": "TOKEN_B"},
    }))
    monkeypatch.setenv("FACEBOOK_ACCOUNTS_FILE", str(accounts_file))

    m = Manager()
    a = m._api("brand_a")
    assert a.page_id == "PAGE_A"
    assert a.access_token == "TOKEN_A"
    assert a.base_url == "https://graph.facebook.com/v20.0"

    b = m._api("brand_b")
    assert b.page_id == "PAGE_B"
    assert b.access_token == "TOKEN_B"
    assert b.base_url == f"https://graph.facebook.com/{config.GRAPH_API_VERSION}"


def test_api_caches_client(tmp_path, monkeypatch):
    _clear_account_env(monkeypatch)
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(json.dumps({
        "brand_a": {"page_id": "PAGE_A", "access_token": "TOKEN_A"}}))
    monkeypatch.setenv("FACEBOOK_ACCOUNTS_FILE", str(accounts_file))

    m = Manager()
    assert m._api("brand_a") is m._api("brand_a")


def test_unknown_account_raises_without_leaking_token(tmp_path, monkeypatch):
    _clear_account_env(monkeypatch)
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(json.dumps({
        "brand_a": {"page_id": "PAGE_A", "access_token": "SUPERSECRET_TOKEN"}}))
    monkeypatch.setenv("FACEBOOK_ACCOUNTS_FILE", str(accounts_file))

    m = Manager()
    with pytest.raises(ValueError) as ei:
        m._api("does_not_exist")
    msg = str(ei.value)
    assert "does_not_exist" in msg
    assert "SUPERSECRET_TOKEN" not in msg  # never leak token material


def test_method_routes_to_selected_account(tmp_path, monkeypatch, stub):
    _clear_account_env(monkeypatch)
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(json.dumps({
        "brand_a": {"page_id": "PAGE_A", "access_token": "TOKEN_A"},
        "brand_b": {"page_id": "PAGE_B", "access_token": "TOKEN_B"},
    }))
    monkeypatch.setenv("FACEBOOK_ACCOUNTS_FILE", str(accounts_file))

    m = Manager()
    stub["queue"].append(FakeResponse({"id": "PAGE_B_1"}))
    m.post_to_facebook("hi", account="brand_b")
    call = stub["calls"][0]
    assert call["url"].endswith("/PAGE_B/feed")
    assert call["params"]["access_token"] == "TOKEN_B"

    stub["queue"].append(FakeResponse({"data": []}))
    m.get_page_posts(account="brand_a")
    assert stub["calls"][1]["url"].endswith("/PAGE_A/posts")
    assert stub["calls"][1]["params"]["access_token"] == "TOKEN_A"


def test_default_account_routes_via_legacy_client(monkeypatch, stub):
    """No explicit account + legacy env configured → uses the default account."""
    _clear_account_env(monkeypatch)
    monkeypatch.setattr(config, "PAGE_ID", "LEGACY_PAGE")
    monkeypatch.setattr(config, "PAGE_ACCESS_TOKEN", "LEGACY_TOKEN")

    m = Manager()
    stub["queue"].append(FakeResponse({"id": "ok"}))
    m.post_to_facebook("hi")  # no account → default
    call = stub["calls"][0]
    assert call["url"].endswith("/LEGACY_PAGE/feed")
    assert call["params"]["access_token"] == "LEGACY_TOKEN"


# ── Manager.list_accounts ────────────────────────────────────────────────────

def test_list_accounts_returns_keys_and_page_ids_no_token(tmp_path, monkeypatch):
    _clear_account_env(monkeypatch)
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(json.dumps({
        "brand_a": {"page_id": "PAGE_A", "access_token": "SECRET_A"},
        "brand_b": {"page_id": "PAGE_B", "access_token": "SECRET_B"},
    }))
    monkeypatch.setenv("FACEBOOK_ACCOUNTS_FILE", str(accounts_file))
    monkeypatch.setenv("FACEBOOK_DEFAULT_ACCOUNT", "brand_a")

    listing = Manager().list_accounts()
    assert listing["default"] == "brand_a"
    by_key = {a["account"]: a for a in listing["accounts"]}
    assert by_key["brand_a"]["page_id"] == "PAGE_A"
    assert by_key["brand_b"]["page_id"] == "PAGE_B"

    # No token material anywhere in the serialized listing.
    blob = json.dumps(listing)
    assert "SECRET_A" not in blob
    assert "SECRET_B" not in blob
    assert all(set(a) == {"account", "page_id"} for a in listing["accounts"])
