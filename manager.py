from typing import Any

import config
from facebook_api import FacebookAPI


class Manager:
    def __init__(self):
        # Default-account client, kept for back-compat. Per-account clients are
        # resolved lazily by ``_api`` and cached in ``self._clients``.
        self.api = FacebookAPI()
        self._clients: dict[str, FacebookAPI] = {}

    def _api(self, account: str | None = None) -> FacebookAPI:
        """Return the ``FacebookAPI`` bound to ``account`` (or the default account).

        Accounts come from :func:`config.load_accounts`. Built clients are cached.
        An unknown/absent account raises a clear ``ValueError`` naming the key — the
        message never contains any token material.
        """
        key = account or config.default_account()
        cached = self._clients.get(key)
        if cached is not None:
            return cached

        accounts = config.load_accounts()
        acct = accounts.get(key)
        if acct is None:
            # No explicit account requested and nothing configured → fall back to
            # the legacy default client (back-compat with the single-env setup).
            if not account:
                return self.api
            available = ", ".join(sorted(accounts)) or "(none configured)"
            raise ValueError(
                f"Unknown Facebook account '{key}'. "
                f"Configured accounts: {available}.")

        version = acct.get("graph_api_version") or config.GRAPH_API_VERSION
        client = FacebookAPI(
            page_id=acct.get("page_id"),
            access_token=acct.get("access_token"),
            base_url=f"https://graph.facebook.com/{version}",
        )
        self._clients[key] = client
        return client

    def list_accounts(self) -> dict[str, Any]:
        """List configured accounts (keys + page ids). Never returns token material."""
        accounts = config.load_accounts()
        return {
            "accounts": [
                {"account": key, "page_id": acct.get("page_id")}
                for key, acct in accounts.items()
            ],
            "default": config.default_account(),
        }

    def post_to_facebook(self, message: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).post_message(message)

    def reply_to_comment(self, post_id: str, comment_id: str, message: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).reply_to_comment(comment_id, message)

    def get_page_posts(self, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_posts()

    def get_post_comments(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_comments(post_id)

    def delete_post(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).delete_post(post_id)

    def delete_comment(self, comment_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).delete_comment(comment_id)

    def hide_comment(self, comment_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).hide_comment(comment_id)

    def unhide_comment(self, comment_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).unhide_comment(comment_id)

    def delete_comment_from_post(self, post_id: str, comment_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).delete_comment(comment_id)

    def filter_negative_comments(self, comments: dict[str, Any]) -> list[dict[str, Any]]:
        keywords = ["bad", "terrible", "awful", "hate", "dislike", "problem", "issue"]
        return [c for c in comments.get("data", []) if any(k in c.get("message", "").lower() for k in keywords)]

    def get_number_of_comments(self, post_id: str, account: str | None = None) -> int:
        return len(self._api(account).get_comments(post_id).get("data", []))

    def get_number_of_likes(self, post_id: str, account: str | None = None) -> int:
        return self._api(account)._request("GET", post_id, {"fields": "likes.summary(true)"}).get("likes", {}).get("summary", {}).get("total_count", 0)

    def get_post_insights(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        metrics = [
            "post_impressions", "post_impressions_unique", "post_impressions_paid",
            "post_impressions_organic", "post_engaged_users", "post_clicks",
            "post_reactions_like_total", "post_reactions_love_total", "post_reactions_wow_total",
            "post_reactions_haha_total", "post_reactions_sorry_total", "post_reactions_anger_total",
        ]
        return self._api(account).get_bulk_insights(post_id, metrics)

    def get_post_impressions(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_insights(post_id, "post_impressions")

    def get_post_impressions_unique(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_insights(post_id, "post_impressions_unique")

    def get_post_impressions_paid(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_insights(post_id, "post_impressions_paid")

    def get_post_impressions_organic(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_insights(post_id, "post_impressions_organic")

    def get_post_engaged_users(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_insights(post_id, "post_engaged_users")

    def get_post_clicks(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_insights(post_id, "post_clicks")

    def get_post_reactions_like_total(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_insights(post_id, "post_reactions_like_total")

    def get_post_reactions_love_total(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_insights(post_id, "post_reactions_love_total")

    def get_post_reactions_wow_total(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_insights(post_id, "post_reactions_wow_total")

    def get_post_reactions_haha_total(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_insights(post_id, "post_reactions_haha_total")

    def get_post_reactions_sorry_total(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_insights(post_id, "post_reactions_sorry_total")

    def get_post_reactions_anger_total(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_insights(post_id, "post_reactions_anger_total")

    def get_post_top_commenters(self, post_id: str, account: str | None = None) -> list[dict[str, Any]]:
        # Delegate to get_post_comments so callers/tests can override it; only pass
        # ``account`` when set to stay compatible with single-arg overrides.
        raw = (self.get_post_comments(post_id, account=account) if account
               else self.get_post_comments(post_id))
        comments = raw.get("data", [])
        counter = {}
        for comment in comments:
            user_id = comment.get("from", {}).get("id")
            if user_id:
                counter[user_id] = counter.get(user_id, 0) + 1
        return sorted([{"user_id": k, "count": v} for k, v in counter.items()], key=lambda x: x["count"], reverse=True)

    def post_image_to_facebook(self, image_url: str, caption: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).post_image_to_facebook(image_url, caption)

    def update_post(self, post_id: str, new_message: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).update_post(post_id, new_message)

    def schedule_post(self, message: str, publish_time: int, account: str | None = None) -> dict[str, Any]:
        return self._api(account).schedule_post(message, publish_time)

    def get_page_fan_count(self, account: str | None = None) -> int:
        return self._api(account).get_page_fan_count()

    def get_post_share_count(self, post_id: str, account: str | None = None) -> int:
        return self._api(account).get_post_share_count(post_id)

    def get_post_reactions_breakdown(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        """Return counts for all reaction types on a post."""
        metrics = [
            "post_reactions_like_total",
            "post_reactions_love_total",
            "post_reactions_wow_total",
            "post_reactions_haha_total",
            "post_reactions_sorry_total",
            "post_reactions_anger_total",
        ]
        raw = self._api(account).get_bulk_insights(post_id, metrics)
        results: dict[str, Any] = {}
        for item in raw.get("data", []):
            name = item.get("name")
            value = item.get("values", [{}])[0].get("value")
            results[name] = value
        return results

    def bulk_delete_comments(self, comment_ids: list[str], account: str | None = None) -> list[dict[str, Any]]:
        """Delete multiple comments and return their results."""
        api = self._api(account)
        results = []
        for cid in comment_ids:
            res = api.delete_comment(cid)
            results.append({"comment_id": cid, "result": res})
        return results

    def bulk_hide_comments(self, comment_ids: list[str], account: str | None = None) -> list[dict[str, Any]]:
        """Hide multiple comments and return their results."""
        api = self._api(account)
        results = []
        for cid in comment_ids:
            res = api.hide_comment(cid)
            results.append({"comment_id": cid, "result": res})
        return results

    def bulk_unhide_comments(self, comment_ids: list[str], account: str | None = None) -> list[dict[str, Any]]:
        """Unhide multiple comments and return their results."""
        api = self._api(account)
        results = []
        for cid in comment_ids:
            res = api.unhide_comment(cid)
            results.append({"comment_id": cid, "result": res})
        return results

    def get_comment_replies(self, comment_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_comment_replies(comment_id)

    def get_post_permalink(self, post_id: str, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_post_permalink(post_id)

    def get_scheduled_posts(self, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_scheduled_posts()

    def get_page_info(self, account: str | None = None) -> dict[str, Any]:
        return self._api(account).get_page_info()
