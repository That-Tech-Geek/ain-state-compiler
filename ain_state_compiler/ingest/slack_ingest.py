"""
Slack Ingestor — Full History Edition
======================================
Pulls EVERY message ever posted in the workspace, including:
  - All public and private channels the bot token can access
  - All thread replies (conversations.replies for each threaded message)
  - Direct messages and group DMs (if bot has im:history scope)
  - Archived channels

Pagination: cursor-based, 1000 messages per page, resumes from checkpoint.
Rate limits: Tier 3 (50+ RPM). We use 1.2s sleep per page + exponential
             backoff on 429 responses.

Scopes required on the Slack App:
  channels:history, channels:read
  groups:history, groups:read
  im:history, mpim:history

Zero external dependencies -- stdlib urllib only.

Usage:
    from ain_state_compiler.ingest.slack_ingest import ingest_slack
    from ain_state_compiler.ingest.checkpoint import Checkpoint

    cp = Checkpoint(project_dir)
    messages = ingest_slack(
        token,
        checkpoint=cp,
        fetch_threads=True,
        full_history=False,   # True = ignore checkpoint, fetch from epoch
        progress=True,
    )
"""

import os
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Optional


SLACK_API = "https://slack.com/api"
PAGE_SIZE = 1000          # max messages per page (Slack allows up to 1000)
SLEEP_BETWEEN_PAGES = 1.2   # Tier 3 rate limit: 50+ RPM
SLEEP_BETWEEN_CHANNELS = 0.5


def _slack_get(token: str, method: str, params: Optional[dict] = None) -> dict:
    """Make a GET request to the Slack Web API. Returns parsed JSON dict."""
    url = f"{SLACK_API}/{method}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _with_retry(fn, max_retries=5):
    """
    Calls fn() with exponential backoff on Slack rate-limit (429) errors.
    fn must return a dict with 'ok' key.
    """
    delay = 60
    for attempt in range(max_retries):
        result = fn()
        if result.get("ok"):
            return result
        err = result.get("error", "")
        if err == "ratelimited":
            retry_after = int(result.get("retry_after", delay))
            print(f"[!] Slack rate limited. Waiting {retry_after}s... (attempt {attempt+1}/{max_retries})")
            time.sleep(retry_after + 1)
            delay = min(delay * 2, 300)
            continue
        return result   # other error — return immediately
    return result


def fetch_all_channels(token: str) -> list:
    """
    Returns list of all channel dicts the bot token can access.
    Paginates through conversations.list automatically.
    Types: public_channel, private_channel, mpim, im
    """
    channels = []
    cursor = ""
    while True:
        params = {
            "limit": 200,
            "types": "public_channel,private_channel,mpim,im",
            "exclude_archived": "false",
        }
        if cursor:
            params["cursor"] = cursor

        data = _slack_get(token, "conversations.list", params)

        if not data.get("ok"):
            print(f"[!] Slack conversations.list error: {data.get('error', 'unknown')}")
            break

        batch = data.get("channels", [])
        channels.extend(batch)

        meta = data.get("response_metadata", {})
        cursor = meta.get("next_cursor", "")
        if not cursor:
            break
        time.sleep(SLEEP_BETWEEN_CHANNELS)

    return channels


def fetch_channel_history(
    token: str,
    channel_id: str,
    channel_name: str,
    oldest: str = "0",
    checkpoint_cursor: Optional[str] = None,
) -> tuple:
    """
    Fetches FULL message history for a single channel.
    Paginates from oldest to newest.

    Args:
        token: Slack Bot Token
        channel_id: Slack channel ID (C01234...)
        channel_name: human-readable name for logging
        oldest: Unix timestamp string ("0" = from beginning of time)
        checkpoint_cursor: Resume pagination from this Slack cursor (if resuming)

    Returns:
        (messages: list, final_cursor: str)
        final_cursor is empty string when fully exhausted.
    """
    messages = []
    cursor = checkpoint_cursor or ""
    page = 0
    total_fetched = 0

    while True:
        params = {
            "channel": channel_id,
            "limit": PAGE_SIZE,
            "include_all_metadata": "true",
        }
        if oldest and oldest != "0":
            params["oldest"] = oldest
        if cursor:
            params["cursor"] = cursor

        data = _with_retry(lambda: _slack_get(token, "conversations.history", params))

        if not data.get("ok"):
            err = data.get("error", "unknown")
            if err in ("channel_not_found", "not_in_channel", "missing_scope"):
                break  # skip -- bot not in channel or missing permission
            print(f"[!] conversations.history error for #{channel_name}: {err}")
            break

        batch = data.get("messages", [])
        now = datetime.utcnow().isoformat()
        for msg in batch:
            msg["_channel_id"] = channel_id
            msg["_channel_name"] = channel_name
            msg["_ingested_at"] = now
        messages.extend(batch)
        total_fetched += len(batch)
        page += 1

        # Show progress every 5 pages
        if page % 5 == 0:
            print(f"    #{channel_name}: {total_fetched:,} messages fetched so far...")

        meta = data.get("response_metadata", {})
        next_cursor = meta.get("next_cursor", "")
        if not next_cursor:
            return messages, ""   # fully exhausted

        cursor = next_cursor
        time.sleep(SLEEP_BETWEEN_PAGES)

    return messages, ""


def fetch_thread_replies(
    token: str,
    channel_id: str,
    channel_name: str,
    thread_ts: str,
) -> list:
    """
    Fetches ALL replies in a Slack thread.
    Paginates conversations.replies until exhausted.

    Returns:
        List of reply message dicts (excludes the root message itself).
    """
    replies = []
    cursor = ""

    while True:
        params = {
            "channel": channel_id,
            "ts": thread_ts,
            "limit": PAGE_SIZE,
        }
        if cursor:
            params["cursor"] = cursor

        data = _with_retry(lambda: _slack_get(token, "conversations.replies", params))

        if not data.get("ok"):
            err = data.get("error", "unknown")
            if err in ("thread_not_found", "channel_not_found"):
                break
            print(f"[!] conversations.replies error (ts={thread_ts}): {err}")
            break

        batch = data.get("messages", [])
        now = datetime.utcnow().isoformat()

        # Skip index 0 on first page — that's the root message (already indexed)
        for msg in batch[1:] if not cursor else batch:
            msg["_channel_id"] = channel_id
            msg["_channel_name"] = channel_name
            msg["_thread_ts"] = thread_ts
            msg["_is_reply"] = True
            msg["_ingested_at"] = now
            replies.append(msg)

        meta = data.get("response_metadata", {})
        next_cursor = meta.get("next_cursor", "")
        if not next_cursor:
            break
        cursor = next_cursor
        time.sleep(SLEEP_BETWEEN_PAGES)

    return replies


def ingest_slack(
    token: str,
    since_ts: str = "0",
    fetch_threads: bool = True,
    checkpoint=None,
    full_history: bool = False,
    progress: bool = True,
) -> list:
    """
    Full Slack workspace ingestion — ALL history, ALL channels, ALL threads.

    Args:
        token:         Slack Bot Token (xoxb-...).
        since_ts:      Unix timestamp string. Only used if no checkpoint.
                       Pass "0" (default) to fetch ALL history since epoch.
        fetch_threads: If True, fetch all thread replies (default: True).
        checkpoint:    Checkpoint instance for cursor-based resume.
        full_history:  If True, ignore all checkpoints and fetch from epoch.
        progress:      Print progress messages.

    Returns:
        list of message dicts (channel messages + thread replies, combined).
    """
    if progress:
        print("[*] Slack ingest: listing all accessible channels...")
    channels = fetch_all_channels(token)
    if progress:
        print(f"[+] Found {len(channels)} channels.")

    all_messages = []
    threaded_msgs = []  # messages with reply_count > 0

    for idx, ch in enumerate(channels, 1):
        ch_id = ch.get("id", "")
        ch_name = ch.get("name") or ch.get("user") or ch_id

        # Determine oldest timestamp: checkpoint or full-history or since_ts
        oldest = "0"
        if not full_history and checkpoint:
            # Check if we have a completed cursor for this channel
            saved = checkpoint.load("slack", ch_id)
            if saved:
                oldest = saved
                if progress:
                    print(f"  [{idx}/{len(channels)}] #{ch_name}: resuming from ts={oldest}")
            else:
                oldest = since_ts
                if progress:
                    print(f"  [{idx}/{len(channels)}] #{ch_name}: fetching from ts={oldest}...")
        else:
            if progress:
                print(f"  [{idx}/{len(channels)}] #{ch_name}: full history fetch...")

        msgs, final_cursor = fetch_channel_history(
            token, ch_id, ch_name, oldest=oldest
        )

        # Track threaded messages for reply fetching
        for m in msgs:
            if m.get("reply_count", 0) > 0:
                threaded_msgs.append((ch_id, ch_name, m.get("ts", "")))

        all_messages.extend(msgs)
        if progress:
            print(f"    -> #{ch_name}: {len(msgs):,} messages")

        # Save checkpoint: use the ts of the latest message we fetched
        if checkpoint and msgs:
            latest_ts = max(m.get("ts", "0") for m in msgs)
            checkpoint.save("slack", ch_id, latest_ts)

        time.sleep(SLEEP_BETWEEN_CHANNELS)

    # Fetch thread replies
    if fetch_threads and threaded_msgs:
        if progress:
            print(f"\n[*] Fetching thread replies for {len(threaded_msgs):,} threaded messages...")
        total_replies = 0
        for t_idx, (ch_id, ch_name, thread_ts) in enumerate(threaded_msgs, 1):
            if t_idx % 50 == 0 and progress:
                print(f"    Threads: {t_idx}/{len(threaded_msgs):,} processed, {total_replies:,} replies collected...")
            replies = fetch_thread_replies(token, ch_id, ch_name, thread_ts)
            all_messages.extend(replies)
            total_replies += len(replies)
            time.sleep(0.5)   # courtesy delay between thread fetches
        if progress:
            print(f"[+] Thread replies: {total_replies:,} collected from {len(threaded_msgs):,} threads.")

    if progress:
        print(f"[+] Slack ingest complete. Total: {len(all_messages):,} messages (channels + threads)")

    return all_messages
