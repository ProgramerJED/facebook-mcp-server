"""Shared fixtures. Every test runs against a stubbed ``requests`` — no real Graph
API calls, no real token, no network."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import facebook_api  # noqa: E402
from _fakes import FakeResponse  # noqa: E402

# A realistic-looking (fake) Page token so scrub assertions are meaningful.
FAKE_TOKEN = "EAAsecrettoken1234567890abcdefGHIJ"


@pytest.fixture
def api():
    client = facebook_api.FacebookAPI(
        page_id="PAGE123", access_token=FAKE_TOKEN,
        base_url="https://graph.facebook.com/v22.0", timeout=5, max_retries=2)
    # Treat FAKE_TOKEN as an already-resolved Page token so the lazy Page-token
    # derivation does not insert an extra Graph call ahead of each test's assertions.
    # A dedicated test (test_page_token_derivation) exercises the derivation path with
    # this flag left False.
    client._page_token_resolved = True
    return client


@pytest.fixture
def stub(monkeypatch):
    """Records calls and returns queued responses. Queue items may be a FakeResponse
    or an Exception (raised to simulate a network failure). Empty queue → generic OK.
    ``time.sleep`` is patched out so retry tests never actually wait."""
    calls: list[dict] = []
    queue: list = []

    def fake_request(method, url, params=None, json=None, timeout=None):
        calls.append({"method": method, "url": url, "params": params,
                      "json": json, "timeout": timeout})
        if not queue:
            return FakeResponse({"id": "ok"})
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(facebook_api.requests, "request", fake_request)
    monkeypatch.setattr(facebook_api.time, "sleep", lambda *_a, **_k: None)
    return {"calls": calls, "queue": queue}
