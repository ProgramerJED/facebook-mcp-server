"""Test doubles — a minimal ``requests.Response`` stand-in (no network)."""
from __future__ import annotations

NO_JSON = object()


class FakeResponse:
    def __init__(self, payload, status_code: int = 200, text: str = ""):
        self._payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = text

    def json(self):
        if self._payload is NO_JSON:
            raise ValueError("no json body")
        return self._payload
