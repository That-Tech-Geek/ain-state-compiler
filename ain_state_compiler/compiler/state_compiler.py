"""
State Compiler Module
Aggregates Slack, Jira, and Gmail event streams into executable artifacts:
  - Institutional Memory Modules (IMMs) -- Markdown
  - Operational Execution Graphs (OEGs) -- YAML
  - Active Conflict Reports

100% offline. Zero-LLM dependency at source.
"""

import os
import json
from datetime import datetime
from ain_state_compiler.compiler.conflict_detector import ConflictDetector
from ain_state_compiler.compiler.token_optimizer import TokenOptimizer


class StateCompiler:
    """
    Compiles raw corporate event logs into an executable, internally consistent
    state representation ready for AI agent consumption.

    Usage:
        compiler = StateCompiler(project_dir)
        summary = compiler.compile()

    The compiler writes to project_dir/compiled_state/:
        product_deployment_imm.md
        acme_corp_billing_imm.md
        active_conflicts_report.md
        operational_state.json
        operational_state.yaml
        token_optimization_metrics.json
    """

    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.mock_data_dir = os.path.join(project_dir, "mock_data")
        self.output_dir = os.path.join(project_dir, "compiled_state")
        os.makedirs(self.output_dir, exist_ok=True)

    def load_data(self):
        """Loads Slack, Jira, and Email event logs from JSON files."""
        slack_path = os.path.join(self.mock_data_dir, "slack_history.json")
        jira_path = os.path.join(self.mock_data_dir, "jira_issues.json")
        email_path = os.path.join(self.mock_data_dir, "emails.json")

        with open(slack_path, "r", encoding="utf-8") as f:
            slack_data = json.load(f)
        with open(jira_path, "r", encoding="utf-8") as f:
            jira_data = json.load(f)
        with open(email_path, "r", encoding="utf-8") as f:
            email_data = json.load(f)

        return slack_data, jira_data, email_data

    def compile(self):
        """
        Processes event logs, detects conflicts, and writes compiled artifacts.

        Returns a summary dict with counts and compile timestamp.
        """
        slack_data, jira_data, email_data = self.load_data()

        # Offline contradiction detection (no LLM)
        conflicts = ConflictDetector.detect_conflicts(slack_data, jira_data, email_data)

        # Write IMMs and OEGs
        self.write_product_imm(slack_data, jira_data, email_data, conflicts)
        self.write_billing_imm(slack_data, jira_data, email_data, conflicts)
        self.write_conflicts_report(conflicts)
        self.write_executable_oeg(conflicts)

        return {
            "processed_slack_events": len(slack_data),
            "processed_jira_issues": len(jira_data),
            "processed_emails": len(email_data),
            "detected_conflicts": len(conflicts),
            "compiled_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def write_product_imm(self, slack, jira, emails, conflicts):
        """Compiles the Product Deployment Institutional Memory Module (IMM)."""
        has_conflict = any(c["id"] == "CON-001" for c in conflicts)
        status_str = "DISCREPANCY DETECTED" if has_conflict else "STABLE"

        content = f"""---
title: "Product Deployment State: Analytics v2"
type: "Institutional Memory Module (IMM)"
status: "{status_str}"
last_compiled: "{datetime.now().strftime('%Y-%m-%d')}"
---

# IMM: Product Deployment State - Analytics v2

This module tracks the dynamic deployment state of **Analytics v2**, reconciling
code releases, feature flag overrides, and customer messaging.

## Operational Truth Matrix
* **Jira Tracking (ENG-1043)**: Status `Done` (Code merged, QA approved).
* **Marketing Status (GA Announce)**: Outbound GA announcement broadcasted (marketing@company.com).
* **Production Flag State (Slack)**: `analytics_v2` = **FALSE** (Disabled globally by SRE).

## Active State Conflicts
{"* **WARNING**: SRE disabled the feature flag `analytics_v2` globally to resolve production checkout pool exhaustion. This directly contradicts outbound GA messaging." if has_conflict else "None"}

## Executable SRE Directive
If customer reports loading error or latency spikes on checkout:
1. Confirm feature flag `analytics_v2` is set to **FALSE**.
2. Route connection pool audit logs to SRE channel `#production-alerts`.
"""
        filepath = os.path.join(self.output_dir, "product_deployment_imm.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip())

    def write_billing_imm(self, slack, jira, emails, conflicts):
        """Compiles the Billing Configuration Institutional Memory Module (IMM)."""
        has_conflict = any(c["id"] == "CON-002" for c in conflicts)
        status_str = "DISCREPANCY DETECTED" if has_conflict else "STABLE"

        content = f"""---
title: "Billing Configuration State: Acme Corp"
type: "Institutional Memory Module (IMM)"
status: "{status_str}"
last_compiled: "{datetime.now().strftime('%Y-%m-%d')}"
---

# IMM: Billing Configuration State - Acme Corp

This module tracks signed contract exceptions, support escalations, and active invoicing statuses.

## Operational Truth Matrix
* **Contract Override (Slack)**: Marcus authorized a **35% discount override**.
* **Billing System (Jira BI-402)**: Status `To Do` (Pending setup of standard price $10,000/month).
* **Customer Status (Email EM-903)**: Customer complains regarding invoice discrepancy.

## Active State Conflicts
{"* **WARNING**: VP Sales Marcus approved a 35% discount override, but Jira billing remains configuration-pending, resulting in customer invoice discrepancy." if has_conflict else "None"}

## Executable Pricing Directive
When invoicing Acme Corp:
1. Verify discount approval token `MARCUS_OVERRIDE_35`.
2. Set invoice line total to **$6,500/month** (35% off $10k standard package).
3. Update Jira billing issue status to `Done`.
"""
        filepath = os.path.join(self.output_dir, "acme_corp_billing_imm.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip())

    def write_conflicts_report(self, conflicts):
        """Writes the global active conflicts markdown report."""
        report_md = f"""# Active State Contradictions Report

Last Evaluated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Active Conflicts: {len(conflicts)}

---

"""
        for c in conflicts:
            report_md += f"""## [{c['severity']}] {c['title']} ({c['id']})
* **Category**: {c['category']}
* **Summary**: {c['summary']}
* **Suggested Resolution**: {c['resolution_action']}

### Evidence Collected:
"""
            for ev in c["evidence"]:
                report_md += f"- **{ev['source']}**: {ev['assertion']}\n"
            report_md += "\n---\n\n"

        filepath = os.path.join(self.output_dir, "active_conflicts_report.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report_md.strip())

    def write_executable_oeg(self, conflicts):
        """Compiles the dynamic, token-optimized Operational Execution Graph (OEG) as YAML."""
        oeg_data = {
            "operational_execution_graph": {
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "conflict_disputes": [
                    {
                        "id": c["id"],
                        "category": c["category"],
                        "title": c["title"],
                        "severity": c["severity"],
                        "summary": c["summary"],
                        "evidence": [ev["assertion"] for ev in c["evidence"]],
                        "resolution": c["resolution_action"],
                    }
                    for c in conflicts
                ],
                "active_state_nodes": {
                    "analytics_v2": {
                        "jira_status": "Done",
                        "production_flag": "FALSE",
                        "marketing_claim": "GA_Announced",
                        "operational_status": "PAUSED",
                    },
                    "acme_corp_billing": {
                        "agreed_discount": "35%",
                        "invoiced_amount": "$10,000",
                        "pending_jira": "BI-402",
                        "operational_status": "DISCREPANCY",
                    },
                },
            }
        }

        # Write JSON representation
        json_path = os.path.join(self.output_dir, "operational_state.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(oeg_data, f, indent=2)

        # Compile to optimized YAML
        yaml_str = TokenOptimizer.json_to_yaml(oeg_data)
        yaml_path = os.path.join(self.output_dir, "operational_state.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_str)

        # Write token optimization metrics
        savings = TokenOptimizer.calculate_savings(oeg_data)
        metrics_path = os.path.join(self.output_dir, "token_optimization_metrics.json")
        with open(metrics_path, "w", encoding="utf-8") as f:
            savings_clean = {k: v for k, v in savings.items() if k != "yaml_output"}
            json.dump(savings_clean, f, indent=2)
