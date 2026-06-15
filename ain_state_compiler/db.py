"""
AIN State Compiler -- Bundled Database Initializer
===================================================
This module lives *inside* the installed package so it works regardless of
where the user runs `ain-brain` from. It is the single source of truth for the
SQLite schema and seed data.

Root cause of the previous crash
---------------------------------
The old `init_hivemind_db.py` at the project root used:
    DB_PATH = "cloud_hivemind.db"          # relative path!

That creates the DB in whatever directory Python is executed from.
But `sync.py` resolves the DB via:
    db_path = os.path.join(project_dir, "cloud_hivemind.db")

When the two paths diverge (pip-installed CLI vs. dev checkout) the DB is
either missing or schema-less -- causing `sqlite3.OperationalError: no such
table: slack_history`.

Fix
---
All callers now import `init_db(db_path)` from this module and supply an
explicit absolute path, so there is never any ambiguity.
"""

import os
import sqlite3

# ──────────────────────────────────────────────────────────────────
# Schema SQL -- kept here so both sync.py and the CLI can import it
# ──────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS slack_history (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    channel   TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    user      TEXT NOT NULL,
    text      TEXT NOT NULL,
    thread_ts TEXT DEFAULT '',
    is_reply  INTEGER DEFAULT 0,
    UNIQUE(channel, timestamp)
);

CREATE TABLE IF NOT EXISTS jira_issues (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    status        TEXT NOT NULL,
    assignee      TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    description   TEXT NOT NULL,
    reporter      TEXT DEFAULT '',
    issue_type    TEXT DEFAULT '',
    priority      TEXT DEFAULT '',
    labels        TEXT DEFAULT '',
    comments      TEXT DEFAULT '',
    comment_count INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT '',
    resolution    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS emails (
    id           TEXT PRIMARY KEY,
    subject      TEXT NOT NULL,
    sender       TEXT NOT NULL,
    timestamp    TEXT NOT NULL,
    body         TEXT NOT NULL,
    recipients   TEXT DEFAULT '',
    cc           TEXT DEFAULT '',
    mailbox      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS compile_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    compiled_at  TEXT NOT NULL,
    slack_events INTEGER DEFAULT 0,
    jira_issues  INTEGER DEFAULT 0,
    emails       INTEGER DEFAULT 0,
    conflicts    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sync_checkpoints (
    source      TEXT NOT NULL,
    key         TEXT NOT NULL,
    cursor      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (source, key)
);
"""

_SLACK_SEEDS = [
    ("production-alerts", "2026-06-04T09:15:00Z", "alex_sre",
     "ALERT: Latency spiking on /checkout endpoint. CPU at 95% on primary DB "
     "replica. Checking pool connections."),
    ("production-alerts", "2026-06-04T09:18:00Z", "sara_devops",
     "Checking git blame. The DB leak looks tied to the `analytics-v2` rollout "
     "merged 30 mins ago. It doesn't close pool sessions on exceptions."),
    ("production-alerts", "2026-06-04T09:21:00Z", "alex_sre",
     "Agreed. I am disabling the feature flag `analytics_v2` globally. Rollout "
     "is paused. Checkout latency has normalized back to 45ms."),
    ("production-alerts", "2026-06-04T09:23:00Z", "jared_vp_eng",
     "Confirmed. Do not re-enable `analytics_v2` until we rewrite the connection "
     "pooling hook. Keep the flag set to FALSE."),
    ("sales-leads", "2026-06-04T10:05:00Z", "elena_sales",
     "Acme Corp is willing to close today if we can offer a 35% discount on "
     "Enterprise SaaS. Our standard policy cap is 25%. Can we get an exception?"),
    ("sales-leads", "2026-06-04T10:12:00Z", "marcus_vp_sales",
     "Marcus approved override: Elena is authorized to close Acme Corp with a "
     "35% discount. Standard pricing cap bypassed for this deal."),
]

_JIRA_SEEDS = [
    ("ENG-1043", "Rollout Analytics-v2 Module", "Done", "sara_devops",
     "2026-06-04T09:00:00Z",
     "Deployment of core telemetry trackers. Code merged to main, deployed to "
     "production. Feature flag analytics_v2 toggled ON."),
    ("BI-402", "Configure Acme Corp Billing Account", "To Do", "billing_ops",
     "2026-06-04T08:30:00Z",
     "Set up Acme Corp account on standard enterprise tiers ($10k/month "
     "recurring). Pending approval."),
]

_EMAIL_SEEDS = [
    ("EM-902", "Announcing General Availability of Analytics v2!",
     "marketing@company.com", "2026-06-04T09:30:00Z",
     "Today, we are thrilled to announce that our new Analytics v2 tracking "
     "dashboard is now live and available to all enterprise customers! "
     "Experience real-time latency analytics today."),
    ("EM-903", "Urgent: Acme Corp billing discrepancy",
     "ariel@acme.com", "2026-06-04T10:45:00Z",
     "Hi Support Team, we signed our Enterprise agreement today with Marcus "
     "confirming a 35% discount tier. However, our billing dashboard still "
     "lists the standard $10,000/month recurring invoice. Can you update our "
     "tier before the invoice drafts?"),
]


# ──────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────

def init_db(db_path: str, seed: bool = True, force_reset: bool = False) -> None:
    """
    Create (or repair) the Hivemind SQLite database at *db_path*.

    Args:
        db_path:     Absolute path to the .db file.
        seed:        Insert demo seed rows when True (default).
        force_reset: Drop all tables and re-create from scratch when True.
                     Use sparingly -- this wipes all real data.
    """
    print(f"[*] Initializing Hivemind DB: {db_path}")
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if force_reset:
        cursor.execute("DROP TABLE IF EXISTS slack_history")
        cursor.execute("DROP TABLE IF EXISTS jira_issues")
        cursor.execute("DROP TABLE IF EXISTS emails")
        cursor.execute("DROP TABLE IF EXISTS compile_log")
        print("[*] Dropped existing tables for fresh reset.")

    # Use CREATE TABLE IF NOT EXISTS -- safe to call even on an existing DB
    conn.executescript(_SCHEMA_SQL)

    if seed:
        cursor.executemany(
            "INSERT OR IGNORE INTO slack_history (channel, timestamp, user, text) VALUES (?, ?, ?, ?)",
            _SLACK_SEEDS,
        )
        cursor.executemany(
            "INSERT OR IGNORE INTO jira_issues (id, title, status, assignee, updated_at, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            _JIRA_SEEDS,
        )
        cursor.executemany(
            "INSERT OR IGNORE INTO emails (id, subject, sender, timestamp, body) VALUES (?, ?, ?, ?, ?)",
            _EMAIL_SEEDS,
        )

    conn.commit()
    conn.close()
    print("[+] Hivemind database ready.")


def ensure_schema(db_path: str) -> bool:
    """
    Verify that *db_path* contains the required tables.
    If any table is missing, silently re-runs init_db (non-destructive).

    Returns:
        True if the schema was already valid, False if it had to be repaired.
    """
    if not os.path.exists(db_path):
        init_db(db_path, seed=True)
        return False

    required_tables = {"slack_history", "jira_issues", "emails"}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in cursor.fetchall()}
        conn.close()
    except Exception:
        existing = set()

    if not required_tables.issubset(existing):
        missing = required_tables - existing
        print(f"[!] DB schema incomplete -- missing tables: {missing}. Auto-repairing...")
        init_db(db_path, seed=True, force_reset=False)
        return False

    return True
