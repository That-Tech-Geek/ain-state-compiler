import sqlite3
import os

DB_PATH = "cloud_hivemind.db"

def init_db():
    print(f"[*] Initializing shared Hivemind Cloud Database: {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Drop existing tables
    cursor.execute("DROP TABLE IF EXISTS slack_history")
    cursor.execute("DROP TABLE IF EXISTS jira_issues")
    cursor.execute("DROP TABLE IF EXISTS emails")
    
    # Create Slack table
    cursor.execute("""
    CREATE TABLE slack_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        user TEXT NOT NULL,
        text TEXT NOT NULL,
        UNIQUE(channel, timestamp)
    )
    """)
    
    # Create Jira table
    cursor.execute("""
    CREATE TABLE jira_issues (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        status TEXT NOT NULL,
        assignee TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        description TEXT NOT NULL
    )
    """)
    
    # Create Emails table
    cursor.execute("""
    CREATE TABLE emails (
        id TEXT PRIMARY KEY,
        subject TEXT NOT NULL,
        sender TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        body TEXT NOT NULL
    )
    """)
    
    # Seed Slack Mock Data
    slack_seeds = [
        ("production-alerts", "2026-06-04T09:15:00Z", "alex_sre", "ALERT: Latency spiking on /checkout endpoint. CPU at 95% on primary DB replica. Checking pool connections."),
        ("production-alerts", "2026-06-04T09:18:00Z", "sara_devops", "Checking git blame. The DB leak looks tied to the `analytics-v2` rollout merged 30 mins ago. It doesn't close pool sessions on exceptions."),
        ("production-alerts", "2026-06-04T09:21:00Z", "alex_sre", "Agreed. I am disabling the feature flag `analytics_v2` globally. Rollout is paused. Checkout latency has normalized back to 45ms."),
        ("production-alerts", "2026-06-04T09:23:00Z", "jared_vp_eng", "Confirmed. Do not re-enable `analytics_v2` until we rewrite the connection pooling hook. Keep the flag set to FALSE."),
        ("sales-leads", "2026-06-04T10:05:00Z", "elena_sales", "Acme Corp is willing to close today if we can offer a 35% discount on Enterprise SaaS. Our standard policy cap is 25%. Can we get an exception?"),
        ("sales-leads", "2026-06-04T10:12:00Z", "marcus_vp_sales", "Marcus approved override: Elena is authorized to close Acme Corp with a 35% discount. Standard pricing cap bypassed for this deal.")
    ]
    cursor.executemany("INSERT INTO slack_history (channel, timestamp, user, text) VALUES (?, ?, ?, ?)", slack_seeds)
    
    # Seed Jira Mock Data
    jira_seeds = [
        ("ENG-1043", "Rollout Analytics-v2 Module", "Done", "sara_devops", "2026-06-04T09:00:00Z", "Deployment of core telemetry trackers. Code merged to main, deployed to production. Feature flag analytics_v2 toggled ON."),
        ("BI-402", "Configure Acme Corp Billing Account", "To Do", "billing_ops", "2026-06-04T08:30:00Z", "Set up Acme Corp account on standard enterprise tiers ($10k/month recurring). Pending approval.")
    ]
    cursor.executemany("INSERT INTO jira_issues (id, title, status, assignee, updated_at, description) VALUES (?, ?, ?, ?, ?, ?)", jira_seeds)
    
    # Seed Email Mock Data
    email_seeds = [
        ("EM-902", "Announcing General Availability of Analytics v2!", "marketing@company.com", "2026-06-04T09:30:00Z", "Today, we are thrilled to announce that our new Analytics v2 tracking dashboard is now live and available to all enterprise customers! Experience real-time latency analytics today."),
        ("EM-903", "Urgent: Acme Corp billing discrepancy", "ariel@acme.com", "2026-06-04T10:45:00Z", "Hi Support Team, we signed our Enterprise agreement today with Marcus confirming a 35% discount tier. However, our billing dashboard still lists the standard $10,000/month recurring invoice. Can you update our tier before the invoice drafts?")
    ]
    cursor.executemany("INSERT INTO emails (id, subject, sender, timestamp, body) VALUES (?, ?, ?, ?, ?)", email_seeds)
    
    conn.commit()
    conn.close()
    print("[+] Hivemind database successfully created and seeded.")

if __name__ == "__main__":
    init_db()
