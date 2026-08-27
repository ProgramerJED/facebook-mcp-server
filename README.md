# Facebook MCP Server — Sites Engine hardened fork

An MCP server that lets an agent (Claude, etc.) manage a **single Facebook Page** through
the Meta Graph API: publish and schedule posts, upload images, moderate comments, and read
insights. This is a hardened fork of
[HagaiHen/facebook-mcp-server](https://github.com/HagaiHen/facebook-mcp-server) (MIT),
adapted to the Sites Engine standards.

## What this fork changes (hardening + sanitization)

- **Errors surface, not hide.** The upstream `_request` returned `response.json()` even on
  HTTP 4xx/5xx, so a Graph API error looked like success. Every call now checks the status
  and raises a typed **`FacebookAPIError`** carrying the Meta error code — never a silent
  bad payload.
- **The Page token never leaks.** The token is sent to the Graph API as usual but is
  redacted (`sanitize.scrub`) from every error message / log line — it can't end up in a
  traceback, a URL, or a tool result.
- **Bounded requests.** Every call has a **timeout**, and rate-limit / transient errors
  (HTTP 429, Meta codes 4/17/32/341/613) are **retried with backoff** (configurable).
- **Unsolicited DMs removed.** The `send_dm_to_user` tool was deleted — unsolicited
  Messenger DMs violate Meta policy and need special permissions.
- **Credentials validated + injectable.** A clear error when the token/page id are unset;
  `FacebookAPI(...)` accepts explicit overrides so **tests need no real token or network**.
- **Tests + CI.** A pytest suite (Graph API stubbed — no real calls) and a GitHub Actions
  workflow run on every push/PR.

## Setup

1. Create a **Meta App** and get a long-lived **Page access token** for your Page
   (https://developers.facebook.com/tools/explorer). Production posting needs App Review for
   `pages_manage_posts` + `pages_read_engagement`.
2. Configure the environment (a local `.env` is supported and git-ignored):

   ```env
   FACEBOOK_ACCESS_TOKEN=your_long_lived_page_access_token
   FACEBOOK_PAGE_ID=your_page_id
   # optional
   FACEBOOK_GRAPH_API_VERSION=v22.0
   FACEBOOK_REQUEST_TIMEOUT_SECONDS=15
   FACEBOOK_MAX_RETRIES=2
   ```

3. Install and run:

   ```bash
   pip install -r requirements.txt
   python server.py
   ```

4. Point your MCP client at `server.py` (stdio). The token is read from the environment —
   **never** hard-code it or commit a `.env`.

## Tools

Posting: `post_to_facebook`, `post_image_to_facebook`, `update_post`, `delete_post`,
`schedule_post`, `get_scheduled_posts`, `get_page_posts`, `get_post_permalink`.
Comments: `reply_to_comment`, `get_post_comments`, `get_comment_replies`, `hide_comment`,
`unhide_comment`, `delete_comment`, `bulk_hide_comments`, `bulk_unhide_comments`,
`bulk_delete_comments`, `filter_negative_comments`, `get_post_top_commenters`.
Insights: `get_post_insights` and per-metric variants (impressions total/unique/paid/organic,
engaged users, clicks, reactions), `get_post_reactions_breakdown`, `get_number_of_likes`,
`get_number_of_comments`, `get_post_share_count`, `get_page_fan_count`.
Page: `get_page_info`.

## Development

```bash
pip install -r requirements-dev.txt
pytest -q
```

Tests stub `requests` entirely — they never hit Facebook and need no credentials.

## Security notes

- The Page token is a powerful credential. Keep it only in the environment (or a secrets
  manager), never in the repo, and rotate it if exposed.
- All logs/errors are scrubbed of token-like strings, but treat any output as potentially
  sensitive and avoid piping raw tool results into public channels.

## Attribution & license

Fork of **[HagaiHen/facebook-mcp-server](https://github.com/HagaiHen/facebook-mcp-server)**,
MIT-licensed. This fork keeps the original MIT `LICENSE`; the hardening/tests above are
additional modifications for the Sites Engine project.
