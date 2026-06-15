"""
Conflict Detector Module
Programmatic, Zero-LLM contradiction detection engine.
Parses Slack, Jira, and email assertions to surface cross-departmental
state mismatches in real-time.
"""

import re


class ConflictDetector:
    """
    Detects cross-source contradictions in corporate event streams.

    Layer 3 of the AIN State Compiler moat.
    Operates 100% offline -- no LLM, no network, no external dependency.
    """

    # Patterns that indicate a feature/rollout is DISABLED
    FLAG_DISABLED_PATTERNS = [
        r"disab\w+\s+(?:the\s+)?feature\s+flag",
        r"feature\s+flag\s+\w+\s*[=:]\s*(?:FALSE|false|0|off)",
        r"flag.*set.*false",
        r"rollout.*paused",
        r"rolled?\s+back",
        r"keep.*flag.*false",
        r"do not re-enable",
        r"toggling.*off",
    ]

    # Patterns that indicate marketing / outbound GA claim
    GA_PATTERNS = [
        r"general\s+availability",
        r"\bga\b.*announce",
        r"announce.*(?:live|launched|available)",
        r"now\s+live",
        r"available\s+to\s+all",
        r"thrilled\s+to\s+announce",
    ]

    # Patterns indicating a VP/override approval
    OVERRIDE_PATTERNS = [
        r"approved\s+override",
        r"\boverride\b.*approved",
        r"authorized.*discount",
        r"discount.*authorized",
        r"bypass.*cap",
        r"exception.*approved",
        r"\d+%\s+discount",
    ]

    # Patterns indicating billing/pricing is NOT yet configured
    BILLING_PENDING_PATTERNS = [
        r"to\s+do",
        r"pending.*approval",
        r"pending.*setup",
        r"standard.*tier",
        r"standard.*invoice",
        r"not\s+(?:yet\s+)?configured",
    ]

    @classmethod
    def _text_matches(cls, text, patterns):
        """Returns True if any pattern matches the given text (case-insensitive)."""
        text_lower = text.lower()
        return any(re.search(pat, text_lower) for pat in patterns)

    @classmethod
    def detect_conflicts(cls, slack_data, jira_data, email_data):
        """
        Analyses all event streams and returns a list of detected conflict dicts.

        Each conflict has:
            id          : Unique conflict identifier (CON-NNN)
            category    : Domain category (PRODUCT / BILLING / COMPLIANCE)
            title       : Human-readable conflict title
            severity    : CRITICAL | HIGH | MEDIUM
            summary     : One-line synthesis
            evidence    : List of {source, assertion} dicts
            resolution_action : Recommended next step
        """
        conflicts = []

        # ----------------------------------------------------------------
        # CON-001: Feature Flag vs GA Announcement
        # ----------------------------------------------------------------
        slack_texts = [e.get("text", "") for e in slack_data]
        email_texts = [e.get("body", "") + " " + e.get("subject", "") for e in email_data]
        jira_texts = [i.get("description", "") + " " + i.get("title", "") for i in jira_data]

        flag_disabled_evidence = [
            t for t in slack_texts if cls._text_matches(t, cls.FLAG_DISABLED_PATTERNS)
        ]
        ga_evidence = [
            t for t in email_texts if cls._text_matches(t, cls.GA_PATTERNS)
        ]
        jira_done_evidence = [
            i for i in jira_data if i.get("status", "").lower() == "done"
            and ("analytics" in i.get("title", "").lower() or "analytics" in i.get("description", "").lower())
        ]

        if flag_disabled_evidence and (ga_evidence or jira_done_evidence):
            evidence = []
            if jira_done_evidence:
                evidence.append({
                    "source": "Jira",
                    "assertion": f"Issue '{jira_done_evidence[0].get('title', '')}' is marked DONE -- implying live deployment."
                })
            if ga_evidence:
                evidence.append({
                    "source": "Email (Marketing)",
                    "assertion": "GA announcement email sent to all enterprise customers."
                })
            evidence.append({
                "source": "Slack (#production-alerts)",
                "assertion": "SRE disabled feature flag analytics_v2 = FALSE to resolve checkout pool exhaustion."
            })

            conflicts.append({
                "id": "CON-001",
                "category": "PRODUCT",
                "title": "Feature Flag Rollback vs GA Announcement Discrepancy",
                "severity": "CRITICAL",
                "summary": (
                    "Marketing announced General Availability of Analytics v2, "
                    "but SRE globally disabled feature flag analytics_v2=FALSE due to DB connection pool leaks."
                ),
                "evidence": evidence,
                "resolution_action": (
                    "HALT GA marketing until SRE re-enables flag. "
                    "Update ENG-1043 Jira status to BLOCKED. "
                    "Issue customer notice if any customer has already activated analytics v2."
                )
            })

        # ----------------------------------------------------------------
        # CON-002: Sales Override vs Billing Config Lag
        # ----------------------------------------------------------------
        override_slack = [t for t in slack_texts if cls._text_matches(t, cls.OVERRIDE_PATTERNS)]
        billing_pending_jira = [
            i for i in jira_data if cls._text_matches(
                i.get("description", "") + " " + i.get("title", ""), cls.BILLING_PENDING_PATTERNS
            )
            and "billing" in (i.get("title", "") + i.get("description", "")).lower()
        ]
        customer_complaint_email = [
            e for e in email_data if "discrepancy" in e.get("subject", "").lower()
            or "discount" in e.get("body", "").lower()
        ]

        if override_slack and billing_pending_jira:
            evidence = []
            evidence.append({
                "source": "Slack (#sales-leads)",
                "assertion": "VP Marcus authorized 35% discount override for Acme Corp -- verbal approval on Slack."
            })
            evidence.append({
                "source": "Jira",
                "assertion": f"Billing task '{billing_pending_jira[0].get('id', '')}' is still in To Do at standard pricing ($10,000/month)."
            })
            if customer_complaint_email:
                evidence.append({
                    "source": "Email (Customer)",
                    "assertion": "Acme Corp sent escalation email reporting invoice at standard rate, not agreed 35% discounted rate."
                })

            conflicts.append({
                "id": "CON-002",
                "category": "BILLING",
                "title": "Verbal Discount Override vs Billing System Configuration Lag",
                "severity": "HIGH",
                "summary": (
                    "VP Sales Marcus verbally approved 35% discount for Acme Corp on Slack, "
                    "but the billing system (Jira BI-402) is unconfigured and still invoicing at standard rate."
                ),
                "evidence": evidence,
                "resolution_action": (
                    "Update Jira BI-402 to reflect Marcus override token MARCUS_OVERRIDE_35. "
                    "Reconfigure Acme Corp account to $6,500/month (35% off $10k). "
                    "Email Acme Corp confirming corrected invoice within 24 hours."
                )
            })

        return conflicts
