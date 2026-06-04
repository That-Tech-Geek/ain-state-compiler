# ain-state-compiler

> **The G-Brain Primitive** — A local-first, self-improving Company Brain that continuously compiles Slack, Jira, and Gmail into an executable, conflict-resolved operational state for AI agents.

[![PyPI version](https://img.shields.io/pypi/v/ain-state-compiler.svg)](https://pypi.org/project/ain-state-compiler/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)](https://pypi.org/project/ain-state-compiler/)
[![License: Proprietary](https://img.shields.io/badge/license-proprietary-red.svg)](./LICENSE)
[![Python Test Suite](https://github.com/That-Tech-Geek/ain-state-compiler/actions/workflows/test.yml/badge.svg)](https://github.com/That-Tech-Geek/ain-state-compiler/actions/workflows/test.yml)

---

## What Is This?

Most enterprise knowledge systems offer static storage and RAG over documents.

`ain-state-compiler` solves a harder problem:

> **Continuously compiling an organization's operational reality into an executable, internally consistent state representation.**

The output is not a document retrieval system — it is a **Company Brain**:

| Dimension | Static KB (Notion/Wikis) | AIN State Compiler |
|---|---|---|
| Focus | Storing documents | Maintaining live state |
| Refunds | Refund policy PDF | Actual refund behaviors observed across support logs |
| Engineering | Static runbooks | SRE behavior during actual incident response |
| Workflows | SOP text | Extracted from real event execution traces |

---

## Architecture

```
[ Slack / Jira / Gmail ]
         |
         v
[ Shared Hivemind DB ]   <-- SQLite (local) or Supabase (optional cloud)
         |
         v  (Every 5 minutes, offline cron)
[ sync + state_compiler ]  -- Zero-LLM, 100% offline
         |
    +---------+-----------+
    |         |           |
[IMMs]   [OEGs]    [Conflict Report]
    \         |           /
         [compiled_state/]
              |
    (On-demand query only)
              v
        [ Ollama LLM ]   <-- local gemma3:1b
              |
        [ Agent Action ]
```

**Key Principles:**
- **Zero-LLM at source**: All ingestion, structuring, and conflict detection is 100% offline deterministic code.
- **LLMs on-demand only**: Only invoked when you explicitly query the brain. Context is pre-compiled and token-optimized (14-30% reduction via JSON→YAML).
- **Self-improving**: Notices recurring resolution structures and updates its executable skill library.
- **Shared hivemind**: Multiple team members write to one central DB; all local nodes compile their own state and read from the same source of truth.

---

## Installation

```bash
pip install ain-state-compiler
```

### First-Time Setup

After installing, run the interactive setup wizard:

```bash
ain-brain setup
```

This will guide you through configuring:
- **Slack Bot Token** (`xoxb-...`)
- **Jira URL + API Token**
- **Gmail App Password**
- **Database Backend Choice**:
  - **Local SQLite** (Default, 100% offline, zero cloud setup, bypasses InfoSec review)
  - **Supabase Cloud** (Optional central database for shared cloud state)
  - **External PostgreSQL** (Optional custom databases for on-premise shared state)

All credentials are saved to `.env` in your project directory. Selecting the default Local SQLite option requires zero database setup.

### Install Ollama (Local LLM)

```bash
ain-brain install-ollama
```

This downloads and installs [Ollama](https://ollama.com) and pulls `gemma3:1b`.
LLMs are only called when you query the brain — never during ingestion.

### Register 5-Minute Background Sync

```bash
ain-brain cron
```

- **Windows**: Registers a Windows Task Scheduler task (`AINBrainSync`).
- **Linux/macOS**: Adds a `crontab` entry.

The background task runs `sync + compile` every 5 minutes completely offline.

---

## Usage

### Seed the local database (mock data for testing)

```bash
ain-brain init-db
```

### Run a one-shot sync + compile

```bash
ain-brain sync
```

### Query the Company Brain

```bash
ain-brain query "What is the current deployment status of Analytics v2?"
ain-brain query "What is the billing situation with Acme Corp?"
ain-brain query "Are there any active conflicts in the system?"
```

If Ollama is running, it uses `gemma3:1b` for inference. Otherwise it falls back to the deterministic offline resolver.

### Start the Dashboard Server

```bash
ain-brain server
```

Open [http://localhost:8000](http://localhost:8000) to access the B2B glassmorphic dashboard with:
- Live ingest stream terminal
- Active contradictions panel
- YAML OEG viewer
- Interactive query terminal

---

## Python API

```python
from ain_state_compiler import StateCompiler, ConflictDetector, TokenOptimizer

# Compile operational state
compiler = StateCompiler("/path/to/project")
summary = compiler.compile()
print(summary)
# {'processed_slack_events': 6, 'processed_jira_issues': 2, ..., 'detected_conflicts': 2}

# Token optimization
import json
data = {"key": "value", "nested": {"a": 1, "b": "hello world"}}
savings = TokenOptimizer.calculate_savings(data)
print(f"YAML saves {savings['saving_percentage']}% tokens vs JSON")

# Query the brain
from ain_state_compiler.query import query_brain
answer, node, used_llm = query_brain("What is the analytics v2 flag status?")
print(answer)
```

### Sync with Supabase

Set environment variables (or configure via `ain-brain setup`):

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

Then run:

```bash
ain-brain sync
```

The sync will pull from Supabase and write compiled state back to the `compile_log` table.

---

## Supabase Schema

Run these SQL commands in Supabase SQL Editor to create the required tables:

```sql
CREATE TABLE slack_history (
    id SERIAL PRIMARY KEY,
    channel TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    "user" TEXT NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE jira_issues (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    assignee TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE emails (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    body TEXT NOT NULL
);

CREATE TABLE compile_log (
    id SERIAL PRIMARY KEY,
    compiled_at TEXT NOT NULL,
    slack_events INTEGER,
    jira_issues INTEGER,
    emails INTEGER,
    conflicts INTEGER
);
```

---

## What Gets Compiled

Each sync cycle produces:

| File | Description |
|---|---|
| `compiled_state/product_deployment_imm.md` | Product Deployment Institutional Memory Module |
| `compiled_state/acme_corp_billing_imm.md` | Billing configuration IMM |
| `compiled_state/active_conflicts_report.md` | All detected cross-departmental contradictions |
| `compiled_state/operational_state.json` | Full operational state (JSON) |
| `compiled_state/operational_state.yaml` | Token-optimized YAML (14-30% smaller) |
| `compiled_state/token_optimization_metrics.json` | Compression metrics |

---

## The Contradiction Engine

The primary competitive moat. Instead of exposing raw conflicting data to AI agents (which causes hallucination), the Contradiction Engine resolves state before agents ever see it.

Example detection:

```
[CON-001] CRITICAL: Feature Flag Rollback vs GA Announcement
  - Jira ENG-1043: Status=Done (GA implied)
  - Email: Marketing sent "Analytics v2 is now live!" to all customers
  - Slack: SRE set analytics_v2=FALSE due to DB connection pool exhaustion

Resolution: Halt GA messaging. Update Jira to BLOCKED. Issue customer notice.
```

---

## Token Optimization

Before submitting context to a local LLM, the JSON→YAML optimizer strips brackets, quotes, and separators:

```
JSON: {"key": "value", "nested": {"a": 1}}   (38 chars)
YAML: key: value\nnested:\n  a: 1            (27 chars = 29% smaller)
```

On realistic payloads, this saves **14-30% of tokens**, reducing inference latency and API costs.

---

## Traction

- **Evaluation Deployments**: 5+ active corporate partner evaluations (fully local/on-premise environments).
- **Daily State Compilation Cycles**: ~1,400 compilation runs triggered across test instances.
- **PyPI Downloads**: Initial alpha launch (tracking statistics at [pypistats.org/packages/ain-state-compiler](https://pypistats.org/packages/ain-state-compiler)).

---

## License

Proprietary Source License — see [LICENSE](LICENSE)

---

*Built on the AIN (Autonomous Intelligence Network) architecture. Part of the G-Brain Company Brain research program.*
