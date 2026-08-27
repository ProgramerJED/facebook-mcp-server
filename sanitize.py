"""Redact secret-like tokens from any text before it is logged or surfaced.

The Facebook Graph API takes the Page access token as an ``access_token`` query
parameter, so it can appear inside request URLs and inside ``requests`` exception
messages. Every string that could reach a log, an exception, or a tool result is
passed through :func:`scrub` first so a token is never leaked.
"""
from __future__ import annotations

import re

REDACTED = "<redacted>"

# ``access_token=<value>`` in a URL/query string → keep the key, redact the value.
_ACCESS_TOKEN_PARAM = re.compile(r"(access_token=)[^&\s\"']+", re.IGNORECASE)
# Facebook user/page tokens start with ``EAA`` followed by a long base64-ish blob.
_FB_TOKEN = re.compile(r"\bEAA[A-Za-z0-9]{20,}\b")
# Generic bearer / ak- / sk- secrets (defense in depth).
_BEARER = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)
_KEYLIKE = re.compile(r"\b(?:ak|sk)-[A-Za-z0-9_\-]{6,}", re.IGNORECASE)


def scrub(text: object) -> str:
    """Return ``text`` with any secret-like token replaced by ``<redacted>``."""
    out = str(text if text is not None else "")
    out = _ACCESS_TOKEN_PARAM.sub(r"\1" + REDACTED, out)
    out = _FB_TOKEN.sub(REDACTED, out)
    out = _BEARER.sub("Bearer " + REDACTED, out)
    out = _KEYLIKE.sub(REDACTED, out)
    return out
