# Active State Contradictions Report

Last Evaluated: 2026-06-07 10:37:38
Total Active Conflicts: 2

---

## [CRITICAL] Deployment Status vs Marketing/Engineering Discrepancy (CON-PRD-001)
* **Category**: PRODUCT
* **Summary**: Engineering or SRE disabled a feature flag, but marketing announced it or Jira tracks it as fully done.
* **Suggested Resolution**: Halt marketing, sync with SRE on flag status, and update Jira to BLOCKED if rolled back.

### Evidence Collected:
- **Jira (ENG-1043)**: Issue marked DONE implying live deployment: 'Rollout Analytics-v2 Module Deployment of core telemetry trackers. Code merged to main, deployed to ...'
- **Email (marketing@company.com)**: Outbound GA announcement detected: 'Announcing General Availability of Analytics v2! Today, we are thrilled to announce that our new Ana...'
- **Slack (#production-alerts)**: Feature flag rollback/disable detected: 'Confirmed. Do not re-enable `analytics_v2` until we rewrite the connection pooling hook. Keep the fl...'

---

## [HIGH] Sales Override vs Billing System Configuration Lag (CON-BIL-002)
* **Category**: BILLING
* **Summary**: A pricing override or discount was authorized verbally/on Slack, but the billing system is pending configuration.
* **Suggested Resolution**: Update billing system to reflect the authorized override and notify the customer of the correction.

### Evidence Collected:
- **Slack (#sales-leads)**: Discount/Pricing override authorized: 'Marcus approved override: Elena is authorized to close Acme Corp with a 35% discount. Standard prici...'
- **Jira (BI-402)**: Billing task pending setup or at standard tier: 'Configure Acme Corp Billing Account Set up Acme Corp account on standard enterprise tiers ($10k/mont...'
- **Email (ariel@acme.com)**: Customer escalation regarding invoice discrepancy: 'Urgent: Acme Corp billing discrepancy Hi Support Team, we signed our Enterprise agreement today with...'

---