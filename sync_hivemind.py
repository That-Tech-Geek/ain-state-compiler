import sqlite3
import json
import os
from ain_state_compiler.compiler.state_compiler import StateCompiler

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, "cloud_hivemind.db")
MOCK_DATA_DIR = os.path.join(PROJECT_DIR, "mock_data")

def sync_from_hivemind():
    print(f"[*] Syncing local node state from Hivemind DB: {DB_PATH}...")
    
    if not os.path.exists(DB_PATH):
        print(f"[!] Error: Hivemind database file {DB_PATH} does not exist. Run init_hivemind_db.py first.")
        return False
        
    conn = sqlite3.connect(DB_PATH)
    # Enable dict factory to easily read rows as dictionary maps
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Fetch Slack Events
    cursor.execute("SELECT channel, timestamp, user, text FROM slack_history")
    slack_rows = [dict(row) for row in cursor.fetchall()]
    
    # 2. Fetch Jira Issues
    cursor.execute("SELECT id, title, status, assignee, updated_at, description FROM jira_issues")
    jira_rows = [dict(row) for row in cursor.fetchall()]
    
    # 3. Fetch Emails
    cursor.execute("SELECT id, subject, sender, timestamp, body FROM emails")
    email_rows = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    # 4. Save back to mock JSON files atomically
    os.makedirs(MOCK_DATA_DIR, exist_ok=True)
    
    with open(os.path.join(MOCK_DATA_DIR, "slack_history.json"), "w", encoding="utf-8") as f:
        json.dump(slack_rows, f, indent=2)
        
    with open(os.path.join(MOCK_DATA_DIR, "jira_issues.json"), "w", encoding="utf-8") as f:
        json.dump(jira_rows, f, indent=2)
        
    with open(os.path.join(MOCK_DATA_DIR, "emails.json"), "w", encoding="utf-8") as f:
        json.dump(email_rows, f, indent=2)
        
    print(f"[+] Downloaded: {len(slack_rows)} Slack events, {len(jira_rows)} Jira issues, {len(email_rows)} emails.")
    
    # 5. Execute offline state compilation loop
    print("[*] Recompiling local Organizational State (Offline Mode)...")
    compiler = StateCompiler(PROJECT_DIR)
    summary = compiler.compile()
    print(f"[+] Compilation complete. Conflicts found: {summary['detected_conflicts']}.")
    return True

if __name__ == "__main__":
    sync_from_hivemind()
