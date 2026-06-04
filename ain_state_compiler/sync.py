"""
Hivemind Sync Module
Pulls event streams from the shared central database (SQLite local OR Supabase cloud)
and recompiles the local operational state.

Supabase REST sync is zero-dependency -- uses only urllib.request.
If SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are present in environment or .env,
the sync will pull from Supabase instead of the local SQLite file.
"""

import os
import json
import sqlite3
import urllib.request
import urllib.error


def _load_env_file(project_dir):
    """Reads .env file in project_dir and injects keys into os.environ if not already set."""
    env_path = os.path.join(project_dir, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def _supabase_fetch(supabase_url, service_role_key, table, columns="*"):
    """
    Fetches rows from a Supabase table via the PostgREST REST API.
    Returns list of row dicts, or empty list on failure.

    Uses only stdlib urllib -- zero extra dependencies.
    """
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/{table}?select={columns}"
    req = urllib.request.Request(
        endpoint,
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[!] Supabase HTTP error on table '{table}': {e.code} {e.reason}")
        return []
    except Exception as e:
        print(f"[!] Supabase connection error on table '{table}': {e}")
        return []


def _supabase_upsert(supabase_url, service_role_key, table, rows):
    """
    Upserts a list of row dicts into a Supabase table via REST.
    Used to write compiled state back to the shared cloud database.

    Uses only stdlib urllib -- zero extra dependencies.
    """
    if not rows:
        return True
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/{table}"
    payload = json.dumps(rows).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"[!] Supabase upsert error on table '{table}': {e}")
        return False


def sync_from_hivemind(project_dir=None):
    """
    Main sync entrypoint. Detects Supabase credentials and routes to cloud or local sync.

    Steps:
      1. Load .env for credentials
      2. If SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY exist, pull from Supabase
      3. Else fall back to local SQLite cloud_hivemind.db
      4. Write events to mock_data/ JSON files
      5. Run offline state compilation
      6. If Supabase is active, write compiled state summary back to cloud

    Args:
        project_dir: Root of the ain-state-compiler project. Defaults to CWD.
    """
    if project_dir is None:
        project_dir = os.path.dirname(os.path.abspath(__file__))
        # Walk up to find project root (contains mock_data/)
        for _ in range(4):
            if os.path.isdir(os.path.join(project_dir, "mock_data")):
                break
            project_dir = os.path.dirname(project_dir)

    _load_env_file(project_dir)

    mock_data_dir = os.path.join(project_dir, "mock_data")
    os.makedirs(mock_data_dir, exist_ok=True)

    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    use_supabase = bool(supabase_url and supabase_key)

    if use_supabase:
        print(f"[*] Supabase cloud sync active: {supabase_url}")
        slack_rows = _supabase_fetch(supabase_url, supabase_key, "slack_history")
        jira_rows = _supabase_fetch(supabase_url, supabase_key, "jira_issues")
        email_rows = _supabase_fetch(supabase_url, supabase_key, "emails")
        print(f"[+] Supabase pull: {len(slack_rows)} Slack | {len(jira_rows)} Jira | {len(email_rows)} Emails")
    else:
        db_path = os.path.join(project_dir, "cloud_hivemind.db")
        if not os.path.exists(db_path):
            print(f"[!] No Hivemind DB at {db_path}. Run `ain-brain init-db` first.")
            return False

        print(f"[*] Local SQLite sync: {db_path}")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT channel, timestamp, user, text FROM slack_history")
        slack_rows = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT id, title, status, assignee, updated_at, description FROM jira_issues")
        jira_rows = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT id, subject, sender, timestamp, body FROM emails")
        email_rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        print(f"[+] SQLite pull: {len(slack_rows)} Slack | {len(jira_rows)} Jira | {len(email_rows)} Emails")

    # Write data to local mock JSON files (the state compiler reads these)
    with open(os.path.join(mock_data_dir, "slack_history.json"), "w", encoding="utf-8") as f:
        json.dump(slack_rows, f, indent=2)
    with open(os.path.join(mock_data_dir, "jira_issues.json"), "w", encoding="utf-8") as f:
        json.dump(jira_rows, f, indent=2)
    with open(os.path.join(mock_data_dir, "emails.json"), "w", encoding="utf-8") as f:
        json.dump(email_rows, f, indent=2)

    # Run offline state compilation
    print("[*] Recompiling local Organizational State (Offline, Zero-LLM)...")
    from ain_state_compiler.compiler.state_compiler import StateCompiler
    compiler = StateCompiler(project_dir)
    summary = compiler.compile()
    print(f"[+] Compilation complete. Conflicts detected: {summary['detected_conflicts']}.")

    # Optionally write compilation summary back to Supabase
    if use_supabase:
        summary_row = {
            "compiled_at": summary["compiled_timestamp"],
            "slack_events": summary["processed_slack_events"],
            "jira_issues": summary["processed_jira_issues"],
            "emails": summary["processed_emails"],
            "conflicts": summary["detected_conflicts"],
        }
        _supabase_upsert(supabase_url, supabase_key, "compile_log", [summary_row])
        print("[+] Compilation summary written back to Supabase compile_log table.")

    return True


if __name__ == "__main__":
    sync_from_hivemind()
