"""scrub() must remove every secret-like token shape."""
from sanitize import scrub

TOKEN = "EAAsecrettoken1234567890abcdefGHIJ"


def test_redacts_access_token_query_param():
    out = scrub(f"https://graph.facebook.com/v22.0/PAGE/feed?message=hi&access_token={TOKEN}")
    assert TOKEN not in out
    assert "access_token=<redacted>" in out


def test_redacts_bare_facebook_token():
    out = scrub(f"Invalid OAuth token {TOKEN} for this call")
    assert TOKEN not in out
    assert "<redacted>" in out


def test_redacts_bearer_and_keylike():
    assert "abc.def-ghi" not in scrub("Authorization: Bearer abc.def-ghi")
    assert "sk-abcdef123456" not in scrub("key sk-abcdef123456 leaked")


def test_none_and_non_str_safe():
    assert scrub(None) == ""
    assert scrub(500) == "500"
