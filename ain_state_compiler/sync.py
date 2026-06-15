"""
Hivemind Sync Module
Pulls event streams from the shared central database (SQLite local OR Supabase cloud)
and recompiles the local operational state.

Supabase REST sync is zero-dependency -- uses only urllib.request.
If SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are present in environment or .env,
the sync will pull from Supabase instead of the local SQLite file.
"""

import os
import sys
import json
import sqlite3
import urllib.request
import urllib.error

from ain_state_compiler.db import ensure_schema, init_db as _init_db


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
    ensure_supabase_credentials(project_dir)

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
        # ensure_schema: auto-creates or repairs missing tables -- never crashes
        ensure_schema(db_path)

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


def ensure_supabase_credentials(project_dir):
    """
    On module/device startup, checks if Supabase credentials are set.
    If USE_SUPABASE is set to true/1, or if they are partially set,
    prompts the user to enter them if stdin is interactive.
    Saves them back to .env if inputted.
    """
    _load_env_file(project_dir)
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    use_supabase_env = os.environ.get("USE_SUPABASE", "").strip().lower() in ("true", "1", "yes")

    if (use_supabase_env or (supabase_url and not supabase_key) or (supabase_key and not supabase_url)) and not (supabase_url and supabase_key):
        if sys.stdin.isatty():
            print("\n======================================================")
            print("  Supabase Credentials Required (Hivemind Cloud Mode)")
            print("======================================================")
            try:
                url = input("  Enter Supabase URL (e.g. https://xxx.supabase.co): ").strip()
                key = input("  Enter Supabase Service Role Key (admin/service-role): ").strip()
                if url and key:
                    os.environ["SUPABASE_URL"] = url
                    os.environ["SUPABASE_SERVICE_ROLE_KEY"] = key
                    # Save to .env using standard append/update helper
                    env_path = os.path.join(project_dir, ".env")
                    existing = {}
                    if os.path.exists(env_path):
                        with open(env_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith("#") and "=" in line:
                                    k, _, v = line.partition("=")
                                    existing[k.strip()] = v.strip()
                    existing["SUPABASE_URL"] = url
                    existing["SUPABASE_SERVICE_ROLE_KEY"] = key
                    with open(env_path, "w", encoding="utf-8") as f:
                        f.write("# AIN State Compiler Configuration\n")
                        for k, v in existing.items():
                            f.write(f"{k}={v}\n")
                    print("[+] Supabase credentials saved to .env")
                    return True
            except (KeyboardInterrupt, EOFError):
                print("\n[!] Skipping credential entry.")
        else:
            print("[!] Supabase configured but credentials missing and shell is non-interactive.")
        return False
    return True


def write_to_shared_db(project_dir, slack_records, jira_records, email_records):
    """
    Writes newly ingested records back to the shared central database (SQLite or Supabase).
    Automatically de-duplicates the database on every write.
    """
    _load_env_file(project_dir)
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    use_supabase = bool(supabase_url and supabase_key)

    if use_supabase:
        print(f"[*] Writing to shared cloud DB (Supabase) with de-duplication...")
        # Format records for Supabase tables
        if slack_records:
            formatted_slack = []
            for r in slack_records:
                formatted_slack.append({
                    "channel": r.get("channel", ""),
                    "timestamp": r.get("ts") or r.get("timestamp", ""),
                    "user": r.get("user", ""),
                    "text": r.get("text", "")
                })
            _supabase_upsert(supabase_url, supabase_key, "slack_history", formatted_slack)
            
        if jira_records:
            formatted_jira = []
            for r in jira_records:
                formatted_jira.append({
                    "id": r.get("id", ""),
                    "title": r.get("title", ""),
                    "status": r.get("status", ""),
                    "assignee": r.get("assignee", ""),
                    "updated_at": r.get("updated_at", ""),
                    "description": r.get("description", "")
                })
            _supabase_upsert(supabase_url, supabase_key, "jira_issues", formatted_jira)
            
        if email_records:
            formatted_emails = []
            for r in email_records:
                formatted_emails.append({
                    "id": r.get("id", ""),
                    "subject": r.get("subject", ""),
                    "sender": r.get("sender", ""),
                    "timestamp": r.get("timestamp", ""),
                    "body": r.get("body", "")
                })
            _supabase_upsert(supabase_url, supabase_key, "emails", formatted_emails)
    else:
        db_path = os.path.join(project_dir, "cloud_hivemind.db")
        # ensure_schema handles both missing DB and missing tables gracefully
        ensure_schema(db_path)

        print(f"[*] Writing to shared local DB ({db_path}) with de-duplication...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Insert Slack records using INSERT OR IGNORE (UNIQUE on channel, timestamp)
        if slack_records:
            slack_data = [
                (
                    r.get("_channel_name") or r.get("channel", ""),
                    r.get("ts") or r.get("timestamp", ""),
                    r.get("user", ""),
                    r.get("text", ""),
                    r.get("_thread_ts") or r.get("thread_ts", ""),
                    1 if r.get("_is_reply") else 0,
                )
                for r in slack_records
            ]
            cursor.executemany(
                """INSERT OR IGNORE INTO slack_history
                   (channel, timestamp, user, text, thread_ts, is_reply)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                slack_data,
            )
            
        if jira_records:
            jira_data = [
                (
                    r.get("id", ""),
                    r.get("title", ""),
                    r.get("status", ""),
                    r.get("assignee", ""),
                    r.get("updated", "") or r.get("updated_at", ""),
                    r.get("description", ""),
                    r.get("reporter", ""),
                    r.get("issue_type", ""),
                    r.get("priority", ""),
                    r.get("labels", ""),
                    r.get("comments", ""),
                    r.get("comment_count", 0),
                    r.get("created", "") or r.get("created_at", ""),
                    r.get("resolution", ""),
                )
                for r in jira_records
            ]
            cursor.executemany(
                """INSERT OR IGNORE INTO jira_issues
                   (id, title, status, assignee, updated_at, description,
                    reporter, issue_type, priority, labels, comments,
                    comment_count, created_at, resolution)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                jira_data,
            )
            
        if email_records:
            email_data = [
                (
                    r.get("id", ""),
                    r.get("subject", ""),
                    r.get("sender", ""),
                    r.get("date") or r.get("timestamp", ""),
                    r.get("body", ""),
                    r.get("recipients", ""),
                    r.get("cc", ""),
                    r.get("mailbox", ""),
                )
                for r in email_records
            ]
            cursor.executemany(
                """INSERT OR IGNORE INTO emails
                   (id, subject, sender, timestamp, body, recipients, cc, mailbox)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                email_data,
            )
            
        conn.commit()
        conn.close()
        print("[+] Write and database de-duplication complete.")


if __name__ == "__main__":
    sync_from_hivemind()
