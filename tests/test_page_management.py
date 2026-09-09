"""Issue #2 — Page-management / metadata tools (cover, profile, page info, pin,
photo list/upload). All against the stubbed ``requests`` (no network/token)."""
import json

import pytest

import facebook_api
from _fakes import FakeResponse
from manager import Manager


# ── set_page_profile_picture ─────────────────────────────────────────────────

def test_set_profile_picture_hits_picture_edge(api, stub):
    api.set_page_profile_picture("https://img/logo.jpg")
    call = stub["calls"][0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/PAGE123/picture")
    assert call["params"]["url"] == "https://img/logo.jpg"


# ── set_page_cover (two-step: unpublished upload → attach) ────────────────────

def test_set_cover_uploads_unpublished_then_attaches(api, stub):
    stub["queue"].append(FakeResponse({"id": "PHOTO99"}))   # upload
    stub["queue"].append(FakeResponse({"success": True}))   # attach
    out = api.set_page_cover("https://img/cover.jpg")
    assert out["photo_id"] == "PHOTO99"

    upload, attach = stub["calls"][0], stub["calls"][1]
    assert upload["url"].endswith("/PAGE123/photos")
    assert upload["params"]["url"] == "https://img/cover.jpg"
    assert upload["params"]["published"] is False          # never a feed story
    assert upload["params"]["no_story"] is True
    assert attach["url"].endswith("/PAGE123")
    assert attach["params"]["cover"] == "PHOTO99"           # attached by photo id


def test_set_cover_raises_when_upload_returns_no_id(api, stub):
    stub["queue"].append(FakeResponse({}))  # upload without an id
    with pytest.raises(facebook_api.FacebookAPIError):
        api.set_page_cover("https://img/cover.jpg")
    assert len(stub["calls"]) == 1  # never attempts the attach


# ── update_page_info ─────────────────────────────────────────────────────────

def test_update_page_info_json_encodes_objects(api, stub):
    api.update_page_info({
        "about": "Bienestar que se toma",
        "phone": "+527351042610",
        "location": {"street": "Ing. Mongoy 108", "city": "Cuautla"},
    })
    p = stub["calls"][0]["params"]
    assert stub["calls"][0]["url"].endswith("/PAGE123")
    assert p["about"] == "Bienestar que se toma"       # scalar passes through
    assert p["phone"] == "+527351042610"
    assert json.loads(p["location"]) == {"street": "Ing. Mongoy 108", "city": "Cuautla"}


def test_update_page_info_rejects_unknown_field(api, stub):
    with pytest.raises(facebook_api.FacebookAPIError) as ei:
        api.update_page_info({"about": "x", "keywords": "spam"})
    assert "keywords" in str(ei.value)
    assert stub["calls"] == []  # nothing sent to Graph


def test_update_page_info_requires_a_field(api, stub):
    with pytest.raises(facebook_api.FacebookAPIError):
        api.update_page_info({})
    assert stub["calls"] == []


# ── pin / unpin ──────────────────────────────────────────────────────────────

def test_pin_and_unpin_toggle_is_pinned(api, stub):
    api.pin_post("POST1")
    api.unpin_post("POST1")
    assert stub["calls"][0]["url"].endswith("/POST1")
    assert stub["calls"][0]["params"]["is_pinned"] is True
    assert stub["calls"][1]["params"]["is_pinned"] is False


# ── list_page_photos (normalizes to the largest source) ──────────────────────

def test_list_page_photos_picks_largest_source(api, stub):
    stub["queue"].append(FakeResponse({"data": [
        {"id": "P1", "name": "Marca", "created_time": "2026-09-01T00:00:00+0000",
         "images": [
             {"width": 200, "height": 200, "source": "https://img/small.jpg"},
             {"width": 1200, "height": 1200, "source": "https://img/big.jpg"}]},
        {"id": "P2", "name": None, "created_time": "2026-09-02T00:00:00+0000",
         "images": []},
    ]}))
    out = api.list_page_photos(limit=10)
    call = stub["calls"][0]
    assert call["params"]["type"] == "uploaded"
    assert call["params"]["limit"] == 10
    assert out["photos"][0] == {
        "photo_id": "P1", "caption": "Marca",
        "source_url": "https://img/big.jpg",
        "created_time": "2026-09-01T00:00:00+0000"}
    assert out["photos"][1]["source_url"] is None  # no images → None, not a crash


# ── upload_page_photo ────────────────────────────────────────────────────────

def test_upload_unpublished_sets_no_story(api, stub):
    stub["queue"].append(FakeResponse({"id": "PH1"}))
    out = api.upload_page_photo("https://img/x.jpg")
    p = stub["calls"][0]["params"]
    assert p["published"] is False and p["no_story"] is True
    assert out["photo_id"] == "PH1"


def test_upload_published_with_caption(api, stub):
    stub["queue"].append(FakeResponse({"id": "PH2", "post_id": "PAGE123_5"}))
    api.upload_page_photo("https://img/x.jpg", published=True, caption="hola")
    p = stub["calls"][0]["params"]
    assert p["published"] is True and p["caption"] == "hola"
    assert "no_story" not in p


# ── missing-scope error surfaces (token-safe) ────────────────────────────────

def test_missing_scope_error_is_scrubbed(api, stub):
    from conftest import FAKE_TOKEN
    stub["queue"].append(FakeResponse(
        {"error": {"message": f"(#200) Requires pages_manage_metadata. token={FAKE_TOKEN}",
                   "code": 200}}, status_code=403))
    with pytest.raises(facebook_api.FacebookAPIError) as ei:
        api.set_page_profile_picture("https://img/x.jpg")
    assert ei.value.error_code == 200
    assert FAKE_TOKEN not in str(ei.value)          # token never leaks
    assert "pages_manage_metadata" in str(ei.value)  # actionable reason kept


# ── manager routes per account ───────────────────────────────────────────────

def test_manager_delegates_page_management(api, stub, monkeypatch):
    m = Manager()
    m.api = api
    monkeypatch.setattr(m, "_api", lambda account=None: api)
    stub["queue"].append(FakeResponse({"id": "PHOTOX"}))  # cover upload
    stub["queue"].append(FakeResponse({"success": True}))  # cover attach
    assert m.set_page_cover("https://img/c.jpg")["photo_id"] == "PHOTOX"
    m.pin_post("P1")
    assert stub["calls"][-1]["params"]["is_pinned"] is True
