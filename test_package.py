"""
Package-level test suite verifying the ain_state_compiler package works
when imported from the package namespace (not the old flat compiler/).
"""

import os
import sys
import json

# Ensure we import from the package, not the flat compiler/ directory
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)


def run_tests():
    print("[*] Running ain_state_compiler package verification suite...")

    # 1. Verify package imports
    from ain_state_compiler import StateCompiler, ConflictDetector, TokenOptimizer, __version__
    print(f"[+] Import test passed. Version: {__version__}")

    # 2. Verify state compilation
    compiler = StateCompiler(PROJECT_DIR)
    summary = compiler.compile()

    assert summary["processed_slack_events"] == 6, f"Expected 6 Slack events, got {summary['processed_slack_events']}"
    assert summary["processed_jira_issues"] == 2, f"Expected 2 Jira issues, got {summary['processed_jira_issues']}"
    assert summary["processed_emails"] == 2, f"Expected 2 emails, got {summary['processed_emails']}"
    assert summary["detected_conflicts"] == 2, f"Expected 2 conflicts, got {summary['detected_conflicts']}"
    print("[+] Compilation assertions passed.")

    # 3. Verify conflict report
    conflicts_path = os.path.join(PROJECT_DIR, "compiled_state", "active_conflicts_report.md")
    assert os.path.exists(conflicts_path), "Active conflicts report should be generated."
    with open(conflicts_path, "r", encoding="utf-8") as f:
        report = f.read()
    assert "analytics_v2" in report.lower(), "Should report Analytics v2 anomaly."
    assert "acme" in report.lower(), "Should report Acme pricing anomaly."
    print("[+] Conflict report assertions passed.")

    # 4. Verify token optimization
    metrics_path = os.path.join(PROJECT_DIR, "compiled_state", "token_optimization_metrics.json")
    assert os.path.exists(metrics_path), "Metrics file should be generated."
    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)
    print(f"[i] JSON chars: {metrics['json_characters']} | YAML chars: {metrics['yaml_characters']} | Saving: {metrics['saving_percentage']}%")
    assert metrics["saving_percentage"] > 10.0, f"YAML compression should exceed 10%, got {metrics['saving_percentage']}%"
    print("[+] Token optimizer assertions passed.")

    # 5. Verify sync module imports
    from ain_state_compiler.sync import sync_from_hivemind
    print("[+] Sync module import passed.")

    # 6. Verify CLI imports
    from ain_state_compiler.cli import main
    print("[+] CLI module import passed.")

    # 7. Verify query module imports
    from ain_state_compiler.query import query_brain, _deterministic_resolve
    ans = _deterministic_resolve("conflict")
    assert "CON-001" in ans, "Deterministic resolver should return CON-001."
    print("[+] Query module assertions passed.")

    print("\n[SUCCESS] All package verification checks passed.")
    return True


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
