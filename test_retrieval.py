import os
from ain_state_compiler.ingest.indexer import ContextIndexer
from ain_state_compiler.retrieval import search_context, search_by_tag

def run_tests():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    idx = ContextIndexer(project_dir)
    idx.init_db()

    # Seed with synthetic data
    run_id = idx.start_run("test_source")
    records = [
        {
            "id": "t1",
            "source": "slack",
            "author": "sara_devops",
            "timestamp": "2026-06-15T10:00:00Z",
            "body": "We need to fix the analytics_v2 latency. It is crashing the connection pool.",
            "subject": "latency spike"
        },
        {
            "id": "t2",
            "source": "jira",
            "author": "jared_vp_eng",
            "timestamp": "2026-06-15T11:00:00Z",
            "body": "Rollback analytics_v2 immediately.",
            "subject": "ENG-404"
        }
    ]
    idx.index_batch(records, run_id=run_id)
    idx.finish_run(run_id)

    # Test 1: semantic search
    res = search_context("analytics latency", limit=5, project_dir=project_dir)
    assert "sara_devops" in res, f"Expected sara_devops in semantic search, got: {res}"
    assert "We need to fix the analytics_v2 latency" in res
    print("[PASS] Semantic FTS5 retrieval works")

    # Test 2: tag search
    res_tag = search_by_tag("analytics_v2", limit=5, project_dir=project_dir)
    assert "jared_vp_eng" in res_tag or "sara_devops" in res_tag, f"Expected tag lookup to find analytics_v2, got: {res_tag}"
    print("[PASS] Tag-based retrieval works")

    # Test 3: Large text truncation
    records_large = [
        {
            "id": "t3",
            "source": "email",
            "author": "verbose_bot",
            "timestamp": "2026-06-15T12:00:00Z",
            "body": "word " * 3000, # 15000 chars
            "subject": "huge email"
        }
    ]
    idx.index_batch(records_large)
    res_large = search_context("huge email", limit=1, project_dir=project_dir)
    assert len(res_large) < 3000, f"Expected body to be truncated, but length is {len(res_large)}"
    print("[PASS] Snippet truncation scales securely for LLM context limits")

    # Clean up test index so it doesn't pollute actual db
    idx.close()
    if os.path.exists(idx.db_path):
        os.remove(idx.db_path)

if __name__ == "__main__":
    run_tests()
    print("All retrieval tests passed successfully.")
