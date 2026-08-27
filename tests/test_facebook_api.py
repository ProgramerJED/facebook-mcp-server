"""Hardened Graph API layer: status handling, retries, timeouts, token safety."""
import pytest
import requests

import facebook_api
from _fakes import NO_JSON, FakeResponse
from conftest import FAKE_TOKEN


# ── happy paths / correct endpoints + params ─────────────────────────────────

def test_post_message_success(api, stub):
    stub["queue"].append(FakeResponse({"id": "PAGE123_999"}))
    out = api.post_message("hola")
    assert out == {"id": "PAGE123_999"}
    call = stub["calls"][0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/PAGE123/feed")
    assert call["params"]["message"] == "hola"
    assert call["params"]["access_token"] == FAKE_TOKEN  # token sent to Graph API
    assert call["timeout"] == 5  # every call is bounded


def test_schedule_post_sets_unpublished_and_time(api, stub):
    api.schedule_post("promo", 1893456000)
    p = stub["calls"][0]["params"]
    assert p["published"] is False
    assert p["scheduled_publish_time"] == 1893456000
    assert stub["calls"][0]["url"].endswith("/PAGE123/feed")


def test_post_image_hits_photos(api, stub):
    api.post_image_to_facebook("https://img/x.jpg", "cap")
    call = stub["calls"][0]
    assert call["url"].endswith("/PAGE123/photos")
    assert call["params"]["url"] == "https://img/x.jpg"


def test_bulk_insights_joins_metrics(api, stub):
    api.get_bulk_insights("POST1", ["a", "b", "c"])
    assert stub["calls"][0]["params"]["metric"] == "a,b,c"


# ── error handling (the upstream gap) ────────────────────────────────────────

def test_graph_error_raises_typed_error(api, stub):
    stub["queue"].append(FakeResponse(
        {"error": {"message": "Unsupported get request", "code": 100}},
        status_code=400))
    with pytest.raises(facebook_api.FacebookAPIError) as ei:
        api.get_page_info()
    assert ei.value.status_code == 400
    assert ei.value.error_code == 100


def test_error_message_scrubs_token(api, stub):
    stub["queue"].append(FakeResponse(
        {"error": {"message": f"Invalid OAuth access_token={FAKE_TOKEN}", "code": 190}},
        status_code=400))
    with pytest.raises(facebook_api.FacebookAPIError) as ei:
        api.post_message("x")
    assert FAKE_TOKEN not in ei.value.safe_message
    assert FAKE_TOKEN not in str(ei.value)


def test_non_json_error_body_is_handled(api, stub):
    stub["queue"].append(FakeResponse(NO_JSON, status_code=502, text="Bad Gateway"))
    with pytest.raises(facebook_api.FacebookAPIError):
        api.get_page_info()


def test_network_exception_wrapped(api, stub):
    stub["queue"].append(requests.Timeout("connection timed out"))
    with pytest.raises(facebook_api.FacebookAPIError):
        api.get_page_info()


# ── retry / rate-limit ───────────────────────────────────────────────────────

def test_retries_rate_limit_then_succeeds(api, stub):
    stub["queue"].append(FakeResponse({"error": {"message": "limit", "code": 4}},
                                      status_code=400))
    stub["queue"].append(FakeResponse({"id": "ok"}))
    assert api.post_message("x") == {"id": "ok"}
    assert len(stub["calls"]) == 2  # retried once


def test_http_429_is_retried(api, stub):
    stub["queue"].append(FakeResponse({"error": {"message": "slow down"}},
                                      status_code=429))
    stub["queue"].append(FakeResponse({"id": "ok"}))
    assert api.post_message("x") == {"id": "ok"}
    assert len(stub["calls"]) == 2


def test_retry_exhausted_raises(api, stub):
    for _ in range(5):
        stub["queue"].append(FakeResponse({"error": {"message": "limit", "code": 4}},
                                          status_code=429))
    with pytest.raises(facebook_api.FacebookAPIError):
        api.post_message("x")
    assert len(stub["calls"]) == 3  # max_retries(2) + 1


def test_non_retryable_error_is_immediate(api, stub):
    stub["queue"].append(FakeResponse({"error": {"message": "bad token", "code": 190}},
                                      status_code=400))
    with pytest.raises(facebook_api.FacebookAPIError):
        api.post_message("x")
    assert len(stub["calls"]) == 1  # 190 is not retryable


# ── credential guard ─────────────────────────────────────────────────────────

def test_missing_credentials_raise_before_any_call(stub):
    unconfigured = facebook_api.FacebookAPI(page_id="", access_token="")
    with pytest.raises(facebook_api.FacebookAPIError):
        unconfigured.post_message("x")
    assert stub["calls"] == []  # never hit the network
