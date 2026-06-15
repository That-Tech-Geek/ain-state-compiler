"""
Jira Ingestor — Full History Edition
======================================
Pulls EVERY issue ever created in the Jira workspace, including:
  - All projects (no project filter by default)
  - All issue types (Bug, Story, Epic, Sub-task, etc.)
  - Full comment threads on every issue (paginated separately)
  - ADF (Atlassian Document Format) description converted to plain text

Pagination: JQL startAt-based (100 issues/page). Comments paginated per-issue.
Rate limits: REST API v3 -- courteous 0.3s sleep between pages.

Auth: Basic auth -- base64(email:api_token)
Token: https://id.atlassian.com/manage-profile/security/api-tokens

Zero external dependencies -- stdlib urllib + base64 only.

Usage:
    from ain_state_compiler.ingest.jira_ingest import ingest_jira
    from ain_state_compiler.ingest.checkpoint import Checkpoint

    cp = Checkpoint(project_dir)
    issues = ingest_jira(
        base_url, email, api_token,
        checkpoint=cp,
        full_history=False,
    )
"""

import os
import json
import time
import base64
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Optional


MAX_PER_PAGE = 100
COMMENTS_PER_PAGE = 100
SLEEP_BETWEEN_PAGES = 0.3
SLEEP_BETWEEN_ISSUES = 0.1


def _jira_request(base_url: str, email: str, api_token: str, method: str, path: str, body=None) -> dict:
    """
    Make a Jira REST API request.
    Returns parsed JSON dict or {"error": ...} on failure.
    """
    creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    url = f"{base_url.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        return {"error": f"HTTP {e.code}: {body_bytes.decode('utf-8', errors='replace')[:300]}"}
    except Exception as e:
        return {"error": str(e)}


def fetch_all_comments(base_url: str, email: str, api_token: str, issue_key: str) -> list:
    """
    Fetches ALL comments for a Jira issue, paginating if needed.
    Jira caps the embedded comment list at ~100; this fetches the rest.

    Args:
        base_url: e.g. "https://yourorg.atlassian.net"
        email: Jira account email
        api_token: Jira API token
        issue_key: e.g. "ENG-1234"

    Returns:
        List of comment dicts with {author, body, created, updated}.
    """
    comments = []
    start_at = 0
    total = None

    while True:
        path = f"/rest/api/3/issue/{issue_key}/comment?startAt={start_at}&maxResults={COMMENTS_PER_PAGE}&orderBy=created"
        data = _jira_request(base_url, email, api_token, "GET", path)

        if "error" in data:
            break

        batch = data.get("values") or data.get("comments", [])
        if total is None:
            total = data.get("total", len(batch))

        for c in batch:
            author = (c.get("author") or {}).get("displayName", "")
            body_text = _adf_to_text(c.get("body") or {})
            comments.append({
                "author": author,
                "body": body_text,
                "created": c.get("created", ""),
                "updated": c.get("updated", ""),
            })

        start_at += len(batch)
        if len(batch) == 0 or start_at >= total:
            break
        time.sleep(SLEEP_BETWEEN_PAGES)

    return comments


def fetch_all_issues(
    base_url: str,
    email: str,
    api_token: str,
    jql: str = "ORDER BY created ASC",
    fields: Optional[list] = None,
    checkpoint=None,
    full_history: bool = False,
) -> list:
    """
    Fetches ALL Jira issues matching the JQL query by paginating through results.
    Fetches full comments for each issue separately.

    Args:
        base_url: e.g. "https://yourorg.atlassian.net"
        email: Jira account email
        api_token: Jira API token
        jql: JQL query string (default: all issues, oldest first)
        fields: list of field names to retrieve, or None for all
        checkpoint: Checkpoint instance for resume
        full_history: If True, ignore checkpoints

    Returns:
        List of issue dicts (flattened, with full comments).
    """
    if fields is None:
        fields = [
            "summary", "status", "assignee", "reporter", "priority",
            "issuetype", "project", "description", "comment",
            "created", "updated", "labels", "components", "fixVersions",
            "sprint", "customfield_10014",  # epic link
            "parent", "subtasks", "resolution", "environment",
        ]

    # If checkpoint has a startAt, resume from there
    start_at = 0
    if not full_history and checkpoint:
        saved = checkpoint.load("jira", "startAt")
        if saved:
            try:
                start_at = int(saved)
                print(f"[*] Jira: resuming from issue #{start_at:,}")
            except ValueError:
                pass

    issues = []
    total = None

    while True:
        body = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": MAX_PER_PAGE,
            "fields": fields,
            "expand": ["renderedFields", "names"],
        }

        data = _jira_request(base_url, email, api_token, "POST", "/rest/api/3/search", body)

        if "error" in data:
            print(f"[!] Jira search error: {data['error']}")
            break

        if "errorMessages" in data and data["errorMessages"]:
            print(f"[!] Jira JQL error: {data['errorMessages']}")
            break

        batch = data.get("issues", [])
        if total is None:
            total = data.get("total", 0)
            print(f"    Jira: {total:,} total issues to fetch.")

        now = datetime.utcnow().isoformat()
        for issue in batch:
            issue["_ingested_at"] = now

            # Fetch full comments if truncated
            issue_key = issue.get("key", "")
            comment_data = (issue.get("fields", {}).get("comment") or {})
            comment_total = comment_data.get("total", 0)
            comment_list = comment_data.get("comments", [])

            if comment_total > len(comment_list):
                # Need to paginate comments separately
                full_comments = fetch_all_comments(base_url, email, api_token, issue_key)
                issue["_full_comments"] = full_comments
            else:
                issue["_full_comments"] = []

        issues.extend(batch)
        start_at += len(batch)

        if start_at % 500 == 0 and start_at > 0:
            print(f"    Jira: {start_at:,}/{total:,} issues fetched ({100*start_at//max(total,1)}%)...")

        # Save checkpoint every 100 issues
        if checkpoint and start_at % 100 == 0:
            checkpoint.save("jira", "startAt", str(start_at))

        if len(batch) == 0 or start_at >= (total or 0):
            break

        time.sleep(SLEEP_BETWEEN_PAGES)

    # Final checkpoint: mark as complete
    if checkpoint:
        checkpoint.save("jira", "startAt", str(start_at))

    return issues


def flatten_issue(issue: dict) -> dict:
    """
    Flattens a Jira issue dict into a simplified record suitable for indexing.
    Extracts key fields and converts ADF to plain text.
    Includes full comment thread.
    """
    fields = issue.get("fields", {})

    # Convert ADF description to plain text
    desc = _adf_to_text(fields.get("description") or {})

    # Flatten embedded comment list
    comment_data = (fields.get("comment") or {}).get("comments", [])
    comments_parts = []
    for c in comment_data:
        author = (c.get("author") or {}).get("displayName", "")
        body = _adf_to_text(c.get("body") or {})
        ts = c.get("created", "")
        comments_parts.append(f"[{ts}] {author}: {body}")

    # Append paginated comments (from _full_comments)
    for c in issue.get("_full_comments", []):
        line = f"[{c.get('created','')}] {c.get('author','')}: {c.get('body','')}"
        if line not in comments_parts:   # deduplicate
            comments_parts.append(line)

    return {
        "id": issue.get("key", ""),
        "title": fields.get("summary", ""),
        "status": (fields.get("status") or {}).get("name", ""),
        "assignee": ((fields.get("assignee") or {}).get("displayName") or ""),
        "reporter": ((fields.get("reporter") or {}).get("displayName") or ""),
        "priority": (fields.get("priority") or {}).get("name", ""),
        "issue_type": (fields.get("issuetype") or {}).get("name", ""),
        "project": (fields.get("project") or {}).get("key", ""),
        "description": desc,
        "comments": "\n".join(comments_parts),
        "comment_count": len(comments_parts),
        "labels": ", ".join(fields.get("labels") or []),
        "created": fields.get("created", ""),
        "updated": fields.get("updated", ""),
        "resolution": (fields.get("resolution") or {}).get("name", "Unresolved"),
        "environment": _adf_to_text(fields.get("environment") or {}),
        "ingested_at": issue.get("_ingested_at", ""),
    }


def _adf_to_text(node, depth=0) -> str:
    """
    Recursively converts Atlassian Document Format (ADF) JSON to plain text.
    ADF reference: https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/
    """
    if not node or not isinstance(node, dict):
        return ""
    node_type = node.get("type", "")
    content = node.get("content", [])
    text = node.get("text", "")

    if node_type == "text":
        return text
    if node_type in ("paragraph", "blockquote"):
        inner = "".join(_adf_to_text(c, depth) for c in content)
        return inner + "\n"
    if node_type in ("heading",):
        inner = "".join(_adf_to_text(c, depth) for c in content)
        return inner + "\n"
    if node_type == "bulletList":
        lines = []
        for item in content:
            item_text = "".join(_adf_to_text(c, depth + 1) for c in item.get("content", []))
            lines.append(f"  - {item_text.strip()}")
        return "\n".join(lines) + "\n"
    if node_type == "orderedList":
        lines = []
        for i, item in enumerate(content, 1):
            item_text = "".join(_adf_to_text(c, depth + 1) for c in item.get("content", []))
            lines.append(f"  {i}. {item_text.strip()}")
        return "\n".join(lines) + "\n"
    if node_type == "codeBlock":
        code = "".join(_adf_to_text(c, depth) for c in content)
        return f"```\n{code}\n```\n"
    if node_type == "hardBreak":
        return "\n"
    if node_type == "mention":
        return f"@{node.get('attrs', {}).get('text', 'user')}"
    if node_type == "emoji":
        return node.get('attrs', {}).get('shortName', '')
    # Fallback: recurse over all children
    return "".join(_adf_to_text(c, depth) for c in content)


def ingest_jira(
    base_url: str,
    email: str,
    api_token: str,
    jql: str = "ORDER BY created ASC",
    checkpoint=None,
    full_history: bool = False,
) -> list:
    """
    Full Jira workspace ingestion — ALL issues, ALL comments, ALL time.

    Args:
        base_url:     Jira base URL, e.g. "https://yourorg.atlassian.net"
        email:        Jira account email
        api_token:    Jira API token (https://id.atlassian.com/manage-profile/security/api-tokens)
        jql:          Optional JQL filter (default: all issues, oldest first)
        checkpoint:   Checkpoint instance for cursor-based resume
        full_history: If True, ignore checkpoints and fetch from the very beginning

    Returns:
        List of flattened issue dicts with full comment threads.
    """
    print(f"[*] Jira ingest: {base_url}")
    raw_issues = fetch_all_issues(
        base_url, email, api_token, jql=jql,
        checkpoint=checkpoint, full_history=full_history,
    )
    print(f"[+] Fetched {len(raw_issues):,} Jira issues. Flattening with full comments...")
    flat = [flatten_issue(i) for i in raw_issues]
    print(f"[+] Jira ingest complete. {sum(i.get('comment_count',0) for i in flat):,} total comments indexed.")
    return flat
