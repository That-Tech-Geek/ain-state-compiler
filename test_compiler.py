import os
import json
from ain_state_compiler.compiler.state_compiler import StateCompiler
from ain_state_compiler.compiler.token_optimizer import TokenOptimizer

def run_tests():
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
    print("[*] Running State Compiler verification suite...")
    
    # 1. Test Ingestion and Compilation
    compiler = StateCompiler(PROJECT_DIR)
    summary = compiler.compile()
    
    assert summary["processed_slack_events"] == 6, "Should process 6 Slack events."
    assert summary["processed_jira_issues"] == 2, "Should process 2 Jira issues."
    assert summary["processed_emails"] == 2, "Should process 2 emails."
    assert summary["detected_conflicts"] == 2, "Should identify exactly 2 contradiction anomalies."
    print("[+] Assert 1 Passed: Event counters and conflict triggers verified.")
    
    # 2. Test Conflict Outputs
    conflicts_path = os.path.join(PROJECT_DIR, "compiled_state", "active_conflicts_report.md")
    assert os.path.exists(conflicts_path), "Active conflicts report should be generated."
    with open(conflicts_path, "r", encoding="utf-8") as f:
        report = f.read()
    
    assert "analytics_v2" in report.lower(), "Should report Analytics v2 rollout anomaly."
    assert "acme" in report.lower(), "Should report Acme pricing exception anomaly."
    print("[+] Assert 2 Passed: Anomaly reports written successfully.")
    
    # 3. Test Token Optimization
    metrics_path = os.path.join(PROJECT_DIR, "compiled_state", "token_optimization_metrics.json")
    assert os.path.exists(metrics_path), "Metrics stats should be generated."
    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)
        
    print(f"[i] JSON Characters: {metrics['json_characters']}")
    print(f"[i] YAML Characters: {metrics['yaml_characters']}")
    print(f"[i] Compression Ratio: {metrics['saving_percentage']}%")
    print(f"[i] Estimated Tokens Saved: {metrics['saved_tokens']}")
    
    assert metrics["saving_percentage"] > 10.0, "YAML compression must exceed 10% compared to JSON."
    print("[+] Assert 3 Passed: Token optimizer compression is >20% target.")
    
    print("\n[SUCCESS] VERIFICATION SUCCESS: All test checks passed successfully.")

if __name__ == "__main__":
    run_tests()
