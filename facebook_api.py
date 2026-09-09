"""Thin, hardened wrapper over the Facebook Graph API.

Sanitization/hardening added on top of the upstream project:
- HTTP status is checked; a Graph API error is raised as ``FacebookAPIError`` instead
  of being returned as if it were a successful payload.
- Every request has a timeout; rate-limit / transient errors are retried with backoff.
- The Page access token is never leaked: error text is passed through ``scrub``.
- Credentials are injectable (constructor), so tests need no real token or network.
- The unsolicited-DM tool was removed (Meta policy risk).
"""
from __future__ import annotations

import time
from typing import Any

import requests

import config
from sanitize import scrub

# Meta error codes that are transient / rate-limit related and worth retrying.
_RETRYABLE_ERROR_CODES = {4, 17, 32, 341, 613}


class FacebookAPIError(Exception):
    """A Graph API call failed. Carries only scrubbed, safe context."""

    def __init__(self, message: str, *, status_code: int | None = None,
                 error_code: int | None = None):
        self.status_code = status_code
        self.error_code = error_code
        self.safe_message = scrub(message)
        super().__init__(self.safe_message)


def _safe_json(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {"error": {"message": scrub(response.text)[:300]}}
    return data if isinstance(data, dict) else {"data": data}


class FacebookAPI:
    def __init__(self, *, page_id: str | None = None, access_token: str | None = None,
                 base_url: str | None = None, timeout: float | None = None,
                 max_retries: int | None = None):
        self.page_id = page_id if page_id is not None else config.PAGE_ID
        self.access_token = (access_token if access_token is not None
                             else config.PAGE_ACCESS_TOKEN)
        self.base_url = base_url or config.GRAPH_API_BASE_URL
        self.timeout = timeout if timeout is not None else config.REQUEST_TIMEOUT_SECONDS
        self.max_retries = (max_retries if max_retries is not None
                            else config.MAX_RETRIES)

    # ── Generic Graph API request (hardened) ──────────────────────────────────
    def _request(self, method: str, endpoint: str, params: dict[str, Any],
                 json: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.access_token or not self.page_id:
            raise FacebookAPIError(
                "Facebook credentials are not configured "
                "(FACEBOOK_ACCESS_TOKEN / FACEBOOK_PAGE_ID).")
        url = f"{self.base_url}/{endpoint}"
        call_params = dict(params or {})
        call_params["access_token"] = self.access_token

        attempt = 0
        while True:
            attempt += 1
            try:
                response = requests.request(method, url, params=call_params,
                                            json=json, timeout=self.timeout)
            except requests.RequestException as exc:
                raise FacebookAPIError(
                    f"HTTP request to Facebook failed: {exc}") from None

            data = _safe_json(response)
            error = data.get("error") if isinstance(data, dict) else None
            if response.ok and not error:
                return data

            code = (error or {}).get("code")
            if attempt <= self.max_retries and (
                    response.status_code == 429 or code in _RETRYABLE_ERROR_CODES):
                time.sleep(min(2.0, 0.5 * (2 ** (attempt - 1))))
                continue

            message = (error or {}).get("message") or f"HTTP {response.status_code}"
            raise FacebookAPIError(message, status_code=response.status_code,
                                   error_code=code)

    # ── posts ─────────────────────────────────────────────────────────────────
    def post_message(self, message: str) -> dict[str, Any]:
        return self._request("POST", f"{self.page_id}/feed", {"message": message})

    def post_image_to_facebook(self, image_url: str, caption: str) -> dict[str, Any]:
        return self._request("POST", f"{self.page_id}/photos",
                             {"url": image_url, "caption": caption})

    def update_post(self, post_id: str, new_message: str) -> dict[str, Any]:
        return self._request("POST", f"{post_id}", {"message": new_message})

    def delete_post(self, post_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"{post_id}", {})

    def schedule_post(self, message: str, publish_time: int) -> dict[str, Any]:
        return self._request("POST", f"{self.page_id}/feed", {
            "message": message, "published": False,
            "scheduled_publish_time": publish_time})

    def get_posts(self) -> dict[str, Any]:
        return self._request("GET", f"{self.page_id}/posts",
                             {"fields": "id,message,created_time"})

    def get_scheduled_posts(self) -> dict[str, Any]:
        return self._request("GET", f"{self.page_id}/scheduled_posts",
                             {"fields": "id,message,scheduled_publish_time"})

    def get_post_permalink(self, post_id: str) -> dict[str, Any]:
        return self._request("GET", f"{post_id}", {"fields": "permalink_url"})

    # ── comments ──────────────────────────────────────────────────────────────
    def reply_to_comment(self, comment_id: str, message: str) -> dict[str, Any]:
        return self._request("POST", f"{comment_id}/comments", {"message": message})

    def get_comments(self, post_id: str) -> dict[str, Any]:
        return self._request("GET", f"{post_id}/comments",
                             {"fields": "id,message,from,created_time"})

    def get_comment_replies(self, comment_id: str) -> dict[str, Any]:
        return self._request("GET", f"{comment_id}/comments",
                             {"fields": "id,message,from,created_time"})

    def delete_comment(self, comment_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"{comment_id}", {})

    def hide_comment(self, comment_id: str) -> dict[str, Any]:
        return self._request("POST", f"{comment_id}", {"is_hidden": True})

    def unhide_comment(self, comment_id: str) -> dict[str, Any]:
        return self._request("POST", f"{comment_id}", {"is_hidden": False})

    # ── insights ──────────────────────────────────────────────────────────────
    def get_insights(self, post_id: str, metric: str,
                     period: str = "lifetime") -> dict[str, Any]:
        return self._request("GET", f"{post_id}/insights",
                             {"metric": metric, "period": period})

    def get_bulk_insights(self, post_id: str, metrics: list[str],
                          period: str = "lifetime") -> dict[str, Any]:
        return self.get_insights(post_id, ",".join(metrics), period)

    def get_reactions(self, post_id: str, reaction_type: str,
                      period: str = "lifetime") -> dict[str, Any]:
        """Per-reaction total via the reactions EDGE (2026 migration).

        Meta removed the ``post_reactions_*_total`` insight metrics; per-reaction
        counts now come from ``GET {post_id}/reactions?type=<TYPE>&
        summary=total_count`` — read ``summary.total_count`` from the payload.
        Graph type tokens: LIKE/LOVE/WOW/HAHA/SAD/ANGRY (SAD<-sorry, ANGRY<-anger).
        """
        return self._request("GET", f"{post_id}/reactions",
                             {"type": reaction_type, "summary": "total_count",
                              "limit": 0})

    # ── page ──────────────────────────────────────────────────────────────────
    def get_page_fan_count(self) -> int:
        # Meta removed the page ``fan_count`` read; ``followers_count`` is the
        # live node field replacement (2026 migration).
        data = self._request("GET", f"{self.page_id}",
                             {"fields": "followers_count"})
        return data.get("followers_count", 0)

    def get_post_share_count(self, post_id: str) -> int:
        # POST node ``shares{count}`` is still valid (only the PAGE-node shares
        # read was removed). ``post_id`` is a post id, so this stays.
        data = self._request("GET", f"{post_id}", {"fields": "shares"})
        return data.get("shares", {}).get("count", 0)

    def get_page_info(self) -> dict[str, Any]:
        fields = "name,about,category,website,emails,phone,description,location"
        return self._request("GET", f"{self.page_id}", {"fields": fields})

    # ── page management / metadata (issue #2) ─────────────────────────────────
    # These write the Page's identity, not its feed. Cover/profile/info need the
    # token to carry ``pages_manage_metadata`` (+ ``business_management``); pin/unpin
    # need ``pages_manage_posts``. A missing scope surfaces as a scrubbed
    # FacebookAPIError (never leaks the token) via ``_request``.

    # Page fields whose value is an object/array and must be JSON-encoded as a form
    # param (scalars — about/phone/website/description — pass through as-is).
    _PAGE_INFO_JSON_FIELDS = {"emails", "hours", "location"}
    _PAGE_INFO_ALLOWED = {
        "about", "description", "phone", "emails", "website", "hours", "location"}

    def set_page_profile_picture(self, image_url: str) -> dict[str, Any]:
        """Set the Page profile picture from a public image URL."""
        return self._request("POST", f"{self.page_id}/picture", {"url": image_url})

    def set_page_cover(self, image_url: str) -> dict[str, Any]:
        """Set the Page cover photo. Two steps: upload the image UNPUBLISHED (so it
        never lands in the feed as a story), then attach the resulting photo id as the
        Page ``cover``. Returns the attach response merged with the ``photo_id``."""
        photo = self._request("POST", f"{self.page_id}/photos",
                             {"url": image_url, "published": False, "no_story": True})
        photo_id = photo.get("id")
        if not photo_id:
            raise FacebookAPIError("cover upload did not return a photo id")
        result = self._request("POST", f"{self.page_id}", {"cover": photo_id})
        return {**result, "photo_id": photo_id}

    def update_page_info(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Update Page contact info / metadata. Allowed keys: about, description,
        phone, emails, website, hours, location. Object/array values (emails, hours,
        location) are JSON-encoded; unknown keys are rejected."""
        import json as _json
        if not fields:
            raise FacebookAPIError("update_page_info requires at least one field")
        unknown = sorted(set(fields) - self._PAGE_INFO_ALLOWED)
        if unknown:
            raise FacebookAPIError(
                "unknown page-info field(s): " + ", ".join(unknown)
                + "; allowed: " + ", ".join(sorted(self._PAGE_INFO_ALLOWED)))
        params: dict[str, Any] = {}
        for key, value in fields.items():
            if key in self._PAGE_INFO_JSON_FIELDS and not isinstance(value, str):
                params[key] = _json.dumps(value)
            else:
                params[key] = value
        return self._request("POST", f"{self.page_id}", params)

    def pin_post(self, post_id: str) -> dict[str, Any]:
        """Pin a post to the top of the Page."""
        return self._request("POST", f"{post_id}", {"is_pinned": True})

    def unpin_post(self, post_id: str) -> dict[str, Any]:
        """Unpin a previously pinned post."""
        return self._request("POST", f"{post_id}", {"is_pinned": False})

    def list_page_photos(self, limit: int = 25) -> dict[str, Any]:
        """List the Page's OWN uploaded photos (type=uploaded) so one can be reused
        as a post image or cover source. Returns
        ``{photos: [{photo_id, caption, source_url, created_time}]}`` — ``source_url``
        is the largest available image for each photo."""
        data = self._request("GET", f"{self.page_id}/photos", {
            "type": "uploaded", "limit": limit,
            "fields": "id,name,created_time,images"})
        photos = []
        for node in data.get("data", []):
            images = node.get("images") or []
            # Graph returns images largest-first; fall back to the first if unsorted.
            source_url = None
            if images:
                largest = max(
                    images, key=lambda im: (im.get("width") or 0) * (im.get("height") or 0))
                source_url = largest.get("source")
            photos.append({
                "photo_id": node.get("id"),
                "caption": node.get("name"),
                "source_url": source_url,
                "created_time": node.get("created_time"),
            })
        return {"photos": photos}

    def upload_page_photo(self, image_url: str, published: bool = False,
                          caption: str = "") -> dict[str, Any]:
        """Upload a photo to the Page — published to the feed, or unpublished
        (``published=False``, the default) so it can be reused as a cover/post source
        without creating a feed story. Returns ``{photo_id, post_id?}``."""
        params: dict[str, Any] = {"url": image_url, "published": published}
        if caption:
            params["caption"] = caption
        if not published:
            params["no_story"] = True
        result = self._request("POST", f"{self.page_id}/photos", params)
        return {"photo_id": result.get("id"), **result}
