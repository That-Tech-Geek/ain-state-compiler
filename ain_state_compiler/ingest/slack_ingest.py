"""
Slack Ingestor
Pulls ALL historical messages from every accessible channel using the
Slack Web API (conversations.list + conversations.history).

API reference: https://docs.slack.dev/reference/methods/conversations.history
Auth: Bot Token (xoxb-...) in Authorization header.
Rate limit: Tier 3 -- 50+ per min. We sleep 1.2s between channel fetches.

Scopes required on the Slack App:
  channels:history, channels:read
  groups:history, groups:read
  im:history, mpim:history

Zero external dependencies -- stdlib urllib only.
"""

import os
import json
import time
import urllib.request
import urllib.error
from datetime import datetime


SLACK_API = "https://slack.com/api"
PAGE_SIZE = 999          # max allowed by API


def _slack_get(token, method, params=None):
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


# Need to import urllib.parse separately for Python 3
import urllib.parse


def fetch_all_channels(token):
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
        time.sleep(0.5)   # respect rate limits

    return channels


def fetch_channel_history(token, channel_id, channel_name, oldest="0"):
    """
    Fetches full message history for a single channel.
    Paginates until exhausted. Returns list of message dicts.
    Each message is augmented with channel_id, channel_name, source_ts.
    """
    messages = []
    cursor = ""
    page = 0

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

        data = _slack_get(token, "conversations.history", params)

        if not data.get("ok"):
            err = data.get("error", "unknown")
            if err == "channel_not_found":
                break  # skip -- bot not in channel
            if err == "ratelimited":
                retry = int(data.get("retry_after", 60))
                print(f"[!] Slack rate limited. Sleeping {retry}s...")
                time.sleep(retry)
                continue
            print(f"[!] conversations.history error for {channel_name}: {err}")
            break

        batch = data.get("messages", [])
        for msg in batch:
            msg["_channel_id"] = channel_id
            msg["_channel_name"] = channel_name
            msg["_ingested_at"] = datetime.utcnow().isoformat()
        messages.extend(batch)
        page += 1

        meta = data.get("response_metadata", {})
        cursor = meta.get("next_cursor", "")
        if not cursor:
            break
        time.sleep(1.2)   # Tier 3: 50+/min = 1 per 1.2s to be safe

    return messages


def ingest_slack(token, since_ts="0"):
    """
    Full Slack workspace ingestion.

    Args:
        token: Slack Bot Token (xoxb-...).
        since_ts: Unix timestamp string. Only fetch messages newer than this.
                  Pass "0" to fetch all history.

    Returns:
        list of message dicts, all channels combined.
    """
    print("[*] Slack ingest: listing all accessible channels...")
    channels = fetch_all_channels(token)
    print(f"[+] Found {len(channels)} channels.")

    all_messages = []
    for ch in channels:
        ch_id = ch.get("id", "")
        ch_name = ch.get("name") or ch.get("user") or ch_id
        print(f"    Fetching #{ch_name} ({ch_id})...")
        msgs = fetch_channel_history(token, ch_id, ch_name, oldest=since_ts)
        all_messages.extend(msgs)
        print(f"    -> {len(msgs)} messages")
        time.sleep(0.5)

    print(f"[+] Slack ingest complete. Total messages: {len(all_messages)}")
    return all_messages
