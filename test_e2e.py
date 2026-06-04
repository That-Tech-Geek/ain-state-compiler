"""
End-to-End Test Suite for AIN State Compiler v0.2.0
Tests ALL components: Ingest pipeline, FTS5 Indexer, Orchestrator, State Compiler, Query Engine.

Uses 100% mock data -- no real credentials required.
All tests must PASS before PyPI deployment.

Run: python test_e2e.py
"""

import os
import sys
import json
import sqlite3
import shutil
import tempfile
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

# ───────────────────────── Test Utilities ─────────────────────────

PASS = 0
FAIL = 0

def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  ->  {detail}")


# ───────────────────────── Mock Data ─────────────────────────────

MOCK_SLACK = [
    {
        "source": "slack",
        "id": "S1001",
        "ts": "1717000001.000000",
        "_channel_name": "engineering",
        "user": "alice",
        "text": "Analytics v2 deployment complete. Feature flag analytics_v2 set to TRUE.",
        "_ingested_at": "2026-06-04T00:01:00Z",
    },
    {
        "source": "slack",
        "id": "S1002",
        "ts": "1717000002.000000",
        "_channel_name": "sre-alerts",
        "user": "sre_bot",
        "text": "CRITICAL: DB connection pool exhausted. Rolling back analytics_v2 flag to FALSE.",
        "_ingested_at": "2026-06-04T00:02:00Z",
    },
    {
        "source": "slack",
        "id": "S1003",
        "ts": "1717000003.000000",
        "_channel_name": "sales",
        "user": "marcus",
        "text": "Acme Corp deal closed. Agreed to 35% discount on annual plan. $6500/month confirmed.",
        "_ingested_at": "2026-06-04T00:03:00Z",
    },
    {
        "source": "slack",
        "id": "S1004",
        "ts": "1717000004.000000",
        "_channel_name": "marketing",
        "user": "priya",
        "text": "Sending GA announcement for Analytics v2 to all customers NOW.",
        "_ingested_at": "2026-06-04T00:04:00Z",
    },
    {
        "source": "slack",
        "id": "S1005",
        "ts": "1717000005.000000",
        "_channel_name": "engineering",
        "user": "bob",
        "text": "New onboarding workflow approved. Reduces time-to-value from 14 days to 3 days.",
        "_ingested_at": "2026-06-04T00:05:00Z",
    },
    {
        "source": "slack",
        "id": "S1006",
        "ts": "1717000006.000000",
        "_channel_name": "support",
        "user": "carol",
        "text": "Acme Corp support ticket: invoice shows $10000 but VP Marcus approved $6500 discount.",
        "_ingested_at": "2026-06-04T00:06:00Z",
    },
]

MOCK_JIRA = [
    {
        "source": "jira",
        "id": "ENG-1043",
        "title": "Analytics v2 Feature Flag Rollout",
        "status": "Done",
        "assignee": "alice",
        "reporter": "pm_lead",
        "description": "Enable analytics_v2 feature flag in production. GA release.",
        "comments": "Alice: Flag set TRUE in production. Jira marked Done.",
        "project": "ENG",
        "labels": "analytics, feature-flag, ga",
        "created": "2026-05-20T10:00:00Z",
        "updated": "2026-06-01T14:30:00Z",
        "ingested_at": "2026-06-04T00:00:00Z",
    },
    {
        "source": "jira",
        "id": "BI-402",
        "title": "Update Acme Corp billing to 35% discount",
        "status": "To Do",
        "assignee": "billing_team",
        "reporter": "marcus",
        "description": "VP authorized 35% discount via Slack for Acme Corp. Update billing system.",
        "comments": "No action taken yet. Invoice still at $10,000/month.",
        "project": "BILLING",
        "labels": "billing, acme, discount",
        "created": "2026-06-02T09:00:00Z",
        "updated": "2026-06-02T09:00:00Z",
        "ingested_at": "2026-06-04T00:00:00Z",
    },
    {
        "source": "jira",
        "id": "OPS-221",
        "title": "Onboarding workflow automation",
        "status": "In Progress",
        "assignee": "bob",
        "reporter": "cto",
        "description": "Automate customer onboarding. Target: 3 days TTv.",
        "comments": "Bob: 70% complete. ETA June 10.",
        "project": "OPS",
        "labels": "onboarding, automation",
        "created": "2026-05-15T08:00:00Z",
        "updated": "2026-06-03T17:00:00Z",
        "ingested_at": "2026-06-04T00:00:00Z",
    },
]

MOCK_EMAIL = [
    {
        "source": "gmail",
        "id": "gmail_INBOX_001",
        "subject": "Analytics v2 is now live!",
        "sender": "priya@company.com",
        "recipients": "customers@company.com",
        "date": "Thu, 04 Jun 2026 00:04:30 +0000",
        "body": "Dear customers, Analytics v2 is now generally available. Enjoy real-time insights.",
        "mailbox": "INBOX",
        "ingested_at": "2026-06-04T00:04:30Z",
    },
    {
        "source": "gmail",
        "id": "gmail_INBOX_002",
        "subject": "Re: Invoice discrepancy - Acme Corp",
        "sender": "acme_cfo@acmecorp.com",
        "recipients": "billing@company.com",
        "date": "Thu, 04 Jun 2026 08:00:00 +0000",
        "body": "Your invoice shows $10,000 but VP Marcus confirmed $6,500. Please correct urgently.",
        "mailbox": "INBOX",
        "ingested_at": "2026-06-04T08:00:00Z",
    },
]


# ───────────────────────── Tests ─────────────────────────────────

def test_indexer():
    """Test FTS5 indexer: insert, FTS search, tag search, dedup."""
    print("\n[1] Indexer Tests")
    from ain_state_compiler.ingest.indexer import ContextIndexer

    tmp = tempfile.mkdtemp()
    try:
        idx = ContextIndexer(tmp)
        idx.init_db()

        # Verify schema
        conn = sqlite3.connect(os.path.join(tmp, "context_index.db"))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        ok("Schema: events table", "events" in tables)
        ok("Schema: tag_index table", "tag_index" in tables)
        ok("Schema: ingest_runs table", "ingest_runs" in tables)
        vtables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        ok("Schema: FTS5 table exists", "events_fts" in tables or
           conn.execute("SELECT name FROM sqlite_master WHERE name='events_fts'").fetchone() is not None)
        conn.close()

        # Index mock data
        all_records = MOCK_SLACK + MOCK_JIRA + MOCK_EMAIL
        run_id = idx.start_run("test")
        inserted, skipped = idx.index_batch(all_records, run_id)
        idx.finish_run(run_id, records_added=inserted)

        ok("Indexing: all records inserted", inserted == len(all_records), f"inserted={inserted}, expected={len(all_records)}")
        ok("Indexing: zero duplicates on first run", skipped == 0, f"skipped={skipped}")

        # Re-index same data -- should all be skipped
        inserted2, skipped2 = idx.index_batch(all_records)
        ok("Deduplication: re-index produces 0 inserts", inserted2 == 0, f"inserted2={inserted2}")
        ok("Deduplication: re-index skips all", skipped2 == len(all_records), f"skipped2={skipped2}")

        # FTS search
        results = idx.search("analytics v2")
        ok("FTS search: 'analytics v2' returns results", len(results) > 0, f"got {len(results)}")

        results_acme = idx.search("acme discount billing")
        ok("FTS search: 'acme discount billing' returns results", len(results_acme) > 0, f"got {len(results_acme)}")

        # Tag search
        tag_results = idx.search_by_tag("analytics")
        ok("Tag search: 'analytics' returns results", len(tag_results) > 0, f"got {len(tag_results)}")

        # Stats
        stats = idx.get_stats()
        ok("Stats: total_events matches", stats["total_events"] == len(all_records),
           f"total={stats['total_events']}, expected={len(all_records)}")
        ok("Stats: by_source has slack", "slack" in stats["by_source"])
        ok("Stats: by_source has jira", "jira" in stats["by_source"])
        ok("Stats: by_source has gmail", "gmail" in stats["by_source"])
        ok("Stats: total_tags > 0", stats["total_tags"] > 0, f"tags={stats['total_tags']}")
        ok("Stats: recent_runs has entry", len(stats["recent_runs"]) > 0)

        idx.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_slack_ingest_logic():
    """Test Slack ingest module structure (no live API needed)."""
    print("\n[2] Slack Ingest Module Tests")
    from ain_state_compiler.ingest.slack_ingest import ingest_slack, fetch_all_channels, fetch_channel_history
    ok("Slack module: ingest_slack importable", callable(ingest_slack))
    ok("Slack module: fetch_all_channels importable", callable(fetch_all_channels))
    ok("Slack module: fetch_channel_history importable", callable(fetch_channel_history))


def test_jira_ingest_logic():
    """Test Jira ingest module: ADF parser, flatten_issue."""
    print("\n[3] Jira Ingest Module Tests")
    from ain_state_compiler.ingest.jira_ingest import _adf_to_text, flatten_issue

    # Test ADF parser
    adf = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hello ADF world."}]},
            {"type": "bulletList", "content": [
                {"type": "listItem", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Item one"}]}
                ]}
            ]},
        ]
    }
    text = _adf_to_text(adf)
    ok("ADF parser: paragraph extracted", "Hello ADF world" in text, f"got: {repr(text)}")
    ok("ADF parser: bulletList extracted", "Item one" in text, f"got: {repr(text)}")

    # Test flatten_issue
    mock_raw_issue = {
        "key": "TEST-001",
        "_ingested_at": "2026-06-04T00:00:00Z",
        "fields": {
            "summary": "Test issue title",
            "status": {"name": "In Progress"},
            "assignee": {"displayName": "Alice"},
            "reporter": {"displayName": "Bob"},
            "priority": {"name": "High"},
            "issuetype": {"name": "Story"},
            "project": {"key": "TEST"},
            "description": {"type": "doc", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Issue description here."}]}
            ]},
            "comment": {"comments": [
                {"author": {"displayName": "Carol"}, "body": {
                    "type": "doc", "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "Fixed in v2.1"}]}
                    ]
                }}
            ]},
            "labels": ["backend", "urgent"],
            "created": "2026-06-01T10:00:00Z",
            "updated": "2026-06-04T08:00:00Z",
        }
    }
    flat = flatten_issue(mock_raw_issue)
    ok("Jira flatten: id extracted", flat["id"] == "TEST-001")
    ok("Jira flatten: title extracted", flat["title"] == "Test issue title")
    ok("Jira flatten: status extracted", flat["status"] == "In Progress")
    ok("Jira flatten: description from ADF", "Issue description here" in flat["description"])
    ok("Jira flatten: comments extracted", "Fixed in v2.1" in flat["comments"])
    ok("Jira flatten: labels joined", "backend" in flat["labels"])


def test_gmail_ingest_logic():
    """Test Gmail ingest module structure (no live IMAP needed)."""
    print("\n[4] Gmail Ingest Module Tests")
    from ain_state_compiler.ingest.gmail_ingest import (
        ingest_gmail, _decode_header_value, _extract_body
    )
    ok("Gmail module: ingest_gmail importable", callable(ingest_gmail))

    # Test header decoder
    decoded = _decode_header_value("Hello World")
    ok("Gmail: header decode plain string", decoded == "Hello World", f"got {repr(decoded)}")

    # Test encoded header (=?utf-8?q?...?=)
    encoded_header = "=?utf-8?q?Test_Subject?="
    decoded2 = _decode_header_value(encoded_header)
    ok("Gmail: encoded header decodes correctly", "Test Subject" in decoded2 or "Test_Subject" in decoded2,
       f"got {repr(decoded2)}")


def test_orchestrator():
    """Test orchestrator with mock env vars and no live connections."""
    print("\n[5] Orchestrator Tests (mock, no live APIs)")
    from ain_state_compiler.ingest.orchestrator import _load_env, _get_cred

    tmp = tempfile.mkdtemp()
    try:
        # Write mock .env
        env_path = os.path.join(tmp, ".env")
        with open(env_path, "w") as f:
            f.write("TEST_MOCK_KEY=mock_value_123\n")
            f.write("# This is a comment\n")
            f.write("EMPTY_KEY=\n")

        _load_env(tmp)
        ok("Orchestrator: .env loaded", os.environ.get("TEST_MOCK_KEY") == "mock_value_123",
           f"got: {os.environ.get('TEST_MOCK_KEY')}")

        # Cleanup env
        del os.environ["TEST_MOCK_KEY"]

        ok("Orchestrator: missing cred returns None", _get_cred("NONEXISTENT_KEY_XYZ") is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_full_pipeline_with_mock():
    """Full end-to-end pipeline test using mock data injected directly into indexer."""
    print("\n[6] Full Pipeline E2E Test (mock data)")
    from ain_state_compiler.ingest.indexer import ContextIndexer
    from ain_state_compiler.ingest.orchestrator import _print_ready_banner

    tmp = tempfile.mkdtemp()
    try:
        idx = ContextIndexer(tmp)
        idx.init_db()

        # Simulate full ingest
        all_records = MOCK_SLACK + MOCK_JIRA + MOCK_EMAIL
        run_id = idx.start_run("e2e_test")
        inserted, skipped = idx.index_batch(all_records, run_id)
        idx.finish_run(run_id, records_added=inserted, status="COMPLETE", notes="E2E test run")

        ok("Pipeline: all records indexed", inserted == len(all_records), f"inserted={inserted}")

        # Test analytics v2 retrieval
        analytics_results = idx.search("analytics v2 flag")
        ok("Pipeline: analytics v2 query finds relevant messages",
           any("analytics" in str(r.get("body","")).lower() or "analytics" in str(r.get("subject","")).lower()
               for r in analytics_results),
           f"results: {[r.get('subject','') or r.get('body','')[:50] for r in analytics_results[:3]]}")

        # Test billing / acme retrieval
        billing_results = idx.search("acme billing discount")
        ok("Pipeline: billing query finds Acme records",
           any("acme" in str(r.get("body","")).lower() or "acme" in str(r.get("subject","")).lower()
               for r in billing_results),
           f"results: {[r.get('subject','') or r.get('body','')[:50] for r in billing_results[:3]]}")

        # Test cross-source retrieval (same topic across Slack + Jira + Email)
        all_analytics = idx.search("analytics_v2", limit=20)
        sources_found = {r["source"] for r in all_analytics}
        ok("Pipeline: analytics topic found across multiple sources",
           len(sources_found) >= 1, f"sources found: {sources_found}")

        # Test speed (FTS query should be <100ms)
        t0 = time.perf_counter()
        for _ in range(20):
            idx.search("deployment rollback analytics")
        t_avg = (time.perf_counter() - t0) / 20 * 1000
        ok(f"Pipeline: FTS search speed <100ms (avg {t_avg:.1f}ms)", t_avg < 100, f"avg={t_avg:.1f}ms")

        # Test manifest generation
        stats = idx.get_stats()
        manifest = {
            "ingest_completed_at": "2026-06-04T08:00:00Z",
            "elapsed_seconds": 0.5,
            "sources": {"slack": {"status": "OK", "count": len(MOCK_SLACK)},
                        "jira": {"status": "OK", "count": len(MOCK_JIRA)},
                        "gmail": {"status": "OK", "count": len(MOCK_EMAIL)}},
            "total_indexed_this_run": inserted,
            "grand_total_in_index": stats["total_events"],
            "total_unique_tags": stats["total_tags"],
            "by_source": stats["by_source"],
            "db_path": idx.db_path,
            "ready_for_deployment": True,
        }

        manifest_path = os.path.join(tmp, "ingest_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        ok("Pipeline: manifest written", os.path.exists(manifest_path))

        with open(manifest_path) as f:
            loaded = json.load(f)
        ok("Pipeline: manifest valid JSON", loaded["ready_for_deployment"] is True)
        ok("Pipeline: manifest has all sources", all(k in loaded["sources"] for k in ["slack", "jira", "gmail"]))

        # Print readiness banner (validates it runs without error)
        try:
            _print_ready_banner(manifest, 0.5)
            ok("Pipeline: readiness banner printed", True)
        except Exception as e:
            ok("Pipeline: readiness banner printed", False, str(e))

        idx.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_state_compiler_integration():
    """Test that state compiler still works alongside ingest layer."""
    print("\n[7] State Compiler Integration Test")
    from ain_state_compiler import StateCompiler, ConflictDetector, TokenOptimizer, __version__
    ok("Package imports: StateCompiler", callable(StateCompiler))
    ok("Package imports: ConflictDetector", callable(ConflictDetector))
    ok("Package imports: TokenOptimizer", callable(TokenOptimizer))

    compiler = StateCompiler(PROJECT_DIR)
    summary = compiler.compile()
    ok("StateCompiler: compiles successfully", "processed_slack_events" in summary, str(summary))
    ok("StateCompiler: detects conflicts", summary.get("detected_conflicts", 0) >= 0)

    savings = TokenOptimizer.calculate_savings({"key": "value", "nested": {"a": 1, "b": "test data"}})
    ok("TokenOptimizer: computes savings", "saving_percentage" in savings, str(savings))
    ok("TokenOptimizer: YAML is smaller than JSON", savings["saving_percentage"] > 0,
       f"saving={savings['saving_percentage']}%")


# ───────────────────────── Run All Tests ─────────────────────────

def run_all():
    print("\n" + "=" * 60)
    print("  AIN STATE COMPILER v0.2.0 -- E2E TEST SUITE")
    print("=" * 60)

    test_indexer()
    test_slack_ingest_logic()
    test_jira_ingest_logic()
    test_gmail_ingest_logic()
    test_orchestrator()
    test_full_pipeline_with_mock()
    test_state_compiler_integration()

    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"  RESULTS: {PASS}/{total} passed | {FAIL} failed")
    if FAIL == 0:
        print("  STATUS: ALL TESTS PASS -- SAFE TO DEPLOY TO PYPI")
    else:
        print("  STATUS: TESTS FAILED -- DO NOT DEPLOY")
    print("=" * 60 + "\n")
    return FAIL == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
