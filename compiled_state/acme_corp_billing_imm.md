---
title: "Billing Configuration State: Acme Corp"
type: "Institutional Memory Module (IMM)"
status: "DISCREPANCY DETECTED"
last_compiled: "2026-06-07"
---

# IMM: Billing Configuration State - Acme Corp

This module tracks signed contract exceptions, support escalations, and active invoicing statuses.

## Operational Truth Matrix
* **Contract Override (Slack)**: Marcus authorized a **35% discount override**.
* **Billing System (Jira BI-402)**: Status `To Do` (Pending setup of standard price $10,000/month).
* **Customer Status (Email EM-903)**: Customer complains regarding invoice discrepancy.

## Active State Conflicts
* **WARNING**: VP Sales Marcus approved a 35% discount override, but Jira billing remains configuration-pending, resulting in customer invoice discrepancy.

## Executable Pricing Directive
When invoicing Acme Corp:
1. Verify discount approval token `MARCUS_OVERRIDE_35`.
2. Set invoice line total to **$6,500/month** (35% off $10k standard package).
3. Update Jira billing issue status to `Done`.