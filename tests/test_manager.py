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
    from _fakes import FakeResponse
    m = Manager()
    m.api = api
    stub["queue"].append(FakeResponse({"data": [
        {"name": "post_reactions_like_total", "values": [{"value": 12}]},
        {"name": "post_reactions_love_total", "values": [{"value": 3}]},
    ]}))
    out = m.get_post_reactions_breakdown("p1")
    assert out["post_reactions_like_total"] == 12
    assert out["post_reactions_love_total"] == 3


def test_unsolicited_dm_tool_removed():
    # Meta policy: unsolicited DMs are not exposed. The surface must be gone.
    assert not hasattr(Manager, "send_dm_to_user")
    assert not hasattr(facebook_api.FacebookAPI, "send_dm_to_user")
