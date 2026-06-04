import os
keys = [
    'SLACK_BOT_TOKEN','JIRA_URL','JIRA_EMAIL','JIRA_API_TOKEN',
    'GMAIL_ADDRESS','GMAIL_APP_PASSWORD',
    'SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY','SUPABASE_ANON_KEY',
    'DB_HOST','DB_NAME','DB_USER'
]
for k in keys:
    val = os.environ.get(k, '')
    status = 'SET' if val else 'NOT SET'
    print(f"{k}: {status}")
