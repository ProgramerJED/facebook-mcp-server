"""Manager helper logic + the removed unsolicited-DM surface."""
import facebook_api
from manager import Manager


def test_filter_negative_comments():
    m = Manager()
    comments = {"data": [
        {"message": "esto es terrible"},   # 'terrible'
        {"message": "great product"},      # clean
        {"message": "I hate it"},          # 'hate'
    ]}
    flagged = m.filter_negative_comments(comments)
    assert len(flagged) == 2


def test_top_commenters_ranking(monkeypatch):
    m = Manager()
    monkeypatch.setattr(m, "get_post_comments", lambda pid: {"data": [
        {"from": {"id": "u1"}}, {"from": {"id": "u1"}}, {"from": {"id": "u2"}}]})
    ranked = m.get_post_top_commenters("p1")
    assert ranked[0] == {"user_id": "u1", "count": 2}
    assert ranked[1] == {"user_id": "u2", "count": 1}


def test_reactions_breakdown(api, stub, monkeypatch):
    """Breakdown reads the reactions EDGE per type (2026 migration), not the
    removed post_reactions_*_total insight metrics."""
    from _fakes import FakeResponse
    m = Manager()
    m.api = api
    # One response per type, in order: LIKE, LOVE, WOW, HAHA, SAD, ANGRY.
    for total in (12, 3, 1, 4, 0, 2):
        stub["queue"].append(FakeResponse({"summary": {"total_count": total}}))
    out = m.get_post_reactions_breakdown("p1")
    assert out == {"like": 12, "love": 3, "wow": 1, "haha": 4, "sorry": 0, "anger": 2}
    # Every call hit the reactions edge with type + summary=total_count.
    reaction_calls = [c for c in stub["calls"] if c["url"].endswith("/p1/reactions")]
    assert len(reaction_calls) == 6
    types = [c["params"]["type"] for c in reaction_calls]
    assert types == ["LIKE", "LOVE", "WOW", "HAHA", "SAD", "ANGRY"]
    for c in reaction_calls:
        assert c["params"]["summary"] == "total_count"
        assert "metric" not in c["params"]


def test_fan_count_reads_followers_count(api, stub):
    """get_page_fan_count reads the live followers_count node field, not the
    removed fan_count."""
    from _fakes import FakeResponse
    m = Manager()
    m.api = api
    stub["queue"].append(FakeResponse({"followers_count": 987, "id": "PAGE123"}))
    assert m.get_page_fan_count() == 987
    call = stub["calls"][0]
    assert call["params"]["fields"] == "followers_count"
    assert "fan_count" not in call["params"]["fields"]


def test_unsolicited_dm_tool_removed():
    # Meta policy: unsolicited DMs are not exposed. The surface must be gone.
    assert not hasattr(Manager, "send_dm_to_user")
    assert not hasattr(facebook_api.FacebookAPI, "send_dm_to_user")
