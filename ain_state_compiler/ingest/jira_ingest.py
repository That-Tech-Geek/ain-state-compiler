"""
Jira Ingestor
Pulls ALL issues from a Jira Cloud instance using the REST API v3.

API reference: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
Endpoint: POST /rest/api/3/search  (JQL search with pagination)
Auth: Basic auth -- base64(email:api_token) in Authorization header.

Pagination: startAt + maxResults (max 100 per page, recommended 50).
JQL: ORDER BY created ASC to get oldest-first, stable pagination.

Zero external dependencies -- stdlib urllib + base64 only.
"""

import os
import json
import time
import base64
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime


MAX_PER_PAGE = 100


def _jira_request(base_url, email, api_token, method, path, body=None):
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


def fetch_all_issues(base_url, email, api_token, jql="ORDER BY created ASC", fields=None):
    """
    Fetches ALL Jira issues matching the JQL query by paginating through results.

    Args:
        base_url: e.g. "https://yourorg.atlassian.net"
        email: Jira account email
        api_token: Jira API token (from https://id.atlassian.com/manage-profile/security/api-tokens)
        jql: JQL query string
        fields: list of field names to retrieve, or None for all

    Returns:
        List of issue dicts.
    """
    if fields is None:
        fields = [
            "summary", "status", "assignee", "reporter", "priority",
            "issuetype", "project", "description", "comment",
            "created", "updated", "labels", "components", "fixVersions",
            "sprint", "customfield_10014",   # epic link
        ]

    issues = []
    start_at = 0
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

        if "errorMessages" in data:
            print(f"[!] Jira JQL error: {data['errorMessages']}")
            break

        batch = data.get("issues", [])
        if total is None:
            total = data.get("total", 0)
            print(f"    Jira: {total} total issues to fetch.")

        for issue in batch:
            issue["_ingested_at"] = datetime.utcnow().isoformat()
        issues.extend(batch)
        start_at += len(batch)

        if len(batch) == 0 or start_at >= total:
            break

        time.sleep(0.3)   # Jira REST API -- be courteous

    return issues


def flatten_issue(issue):
    """
    Flattens a Jira issue dict into a simplified record suitable for indexing.
    Extracts key fields and converts ADF (Atlassian Document Format) description to plain text.
    """
    fields = issue.get("fields", {})

    # Convert ADF description to plain text
    desc = _adf_to_text(fields.get("description") or {})

    # Flatten comment body
    comments = []
    comment_data = (fields.get("comment") or {}).get("comments", [])
    for c in comment_data:
        author = (c.get("author") or {}).get("displayName", "")
        body = _adf_to_text(c.get("body") or {})
        comments.append(f"{author}: {body}")

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
        "comments": "\n".join(comments),
        "labels": ", ".join(fields.get("labels") or []),
        "created": fields.get("created", ""),
        "updated": fields.get("updated", ""),
        "ingested_at": issue.get("_ingested_at", ""),
    }


def _adf_to_text(node, depth=0):
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
    # Fallback: recurse over all children
    return "".join(_adf_to_text(c, depth) for c in content)


def ingest_jira(base_url, email, api_token, jql="ORDER BY created ASC"):
    """
    Full Jira workspace ingestion.

    Args:
        base_url: Jira base URL, e.g. "https://yourorg.atlassian.net"
        email: Jira account email
        api_token: Jira API token
        jql: Optional JQL filter (default: all issues, oldest first)

    Returns:
        List of flattened issue dicts.
    """
    print(f"[*] Jira ingest: {base_url}")
    raw_issues = fetch_all_issues(base_url, email, api_token, jql=jql)
    print(f"[+] Fetched {len(raw_issues)} Jira issues. Flattening...")
    flat = [flatten_issue(i) for i in raw_issues]
    print(f"[+] Jira ingest complete.")
    return flat
