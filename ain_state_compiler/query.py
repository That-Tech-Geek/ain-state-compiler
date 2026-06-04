"""
Query Module
On-demand contextual querying of the compiled Company Brain.

Flow:
  1. Offline keyword-based context selection (no LLM dependency)
  2. Read the matching local IMM markdown / OEG YAML
  3. Submit to local Ollama (gemma3:1b) for inference
  4. If Ollama is offline, fall back to deterministic state resolver

Zero-LLM at source. LLM invoked only on explicit query.
"""

import os
import json
import urllib.request
import urllib.error


def _find_state_dir(project_dir=None):
    """Resolves the compiled_state/ directory from project root."""
    if project_dir is None:
        candidate = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):
            if os.path.isdir(os.path.join(candidate, "compiled_state")):
                return os.path.join(candidate, "compiled_state")
            candidate = os.path.dirname(candidate)
        return os.path.join(os.getcwd(), "compiled_state")
    return os.path.join(project_dir, "compiled_state")


def query_brain(query_text, project_dir=None, model="gemma3:1b"):
    """
    Query the Company Brain.

    Args:
        query_text: Natural language question.
        project_dir: Root of the ain-state-compiler project.
        model: Ollama model name (default: gemma3:1b).

    Returns:
        (answer: str, source_node: str, is_llm: bool)
    """
    state_dir = _find_state_dir(project_dir)

    context_files = {
        "product": os.path.join(state_dir, "product_deployment_imm.md"),
        "billing": os.path.join(state_dir, "acme_corp_billing_imm.md"),
        "conflicts": os.path.join(state_dir, "active_conflicts_report.md"),
        "oeg": os.path.join(state_dir, "operational_state.yaml"),
    }

    # Offline context selection (zero-LLM)
    query_lower = query_text.lower()
    selected_context = ""
    source_node = "global"

    if any(k in query_lower for k in ["product", "flag", "deployment", "analytics", "checkout", "sre", "rollout"]):
        source_node = "product_deployment_imm.md"
        ctx_path = context_files["product"]
    elif any(k in query_lower for k in ["billing", "acme", "discount", "marcus", "price", "invoice", "saas"]):
        source_node = "acme_corp_billing_imm.md"
        ctx_path = context_files["billing"]
    elif any(k in query_lower for k in ["conflict", "mismatch", "discrepancy", "contradiction", "issue"]):
        source_node = "active_conflicts_report.md"
        ctx_path = context_files["conflicts"]
    else:
        source_node = "operational_state.yaml"
        ctx_path = context_files["oeg"]

    if os.path.exists(ctx_path):
        with open(ctx_path, "r", encoding="utf-8") as f:
            selected_context = f.read()
    else:
        selected_context = "No compiled state found. Run `ain-brain sync` to compile first."

    # Build LLM prompt
    prompt = (
        "You are the AIN Company Brain assistant. "
        "Answer the user query using ONLY the provided compiled operational state context. "
        "If the query cannot be answered by the context, state that clearly.\n\n"
        f"[COMPILED CORPORATE CONTEXT]:\n{selected_context}\n\n"
        f"[USER QUERY]:\n{query_text}\n\nAnswer:"
    )

    # Attempt local Ollama inference
    ollama_url = "http://localhost:11434/api/generate"
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        ollama_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            answer = res_data.get("response", "").strip()
            return answer, source_node, True
    except Exception:
        pass

    # Fallback: deterministic state resolver
    fallback = _deterministic_resolve(query_lower)
    return fallback, source_node, False


def _deterministic_resolve(query_lower):
    """Resolves common queries without LLM using hardcoded state facts."""
    if any(k in query_lower for k in ["analytics", "checkout", "flag"]):
        if any(k in query_lower for k in ["status", "flag", "deployed", "live"]):
            return (
                "Per Product Deployment IMM: Analytics v2 is marked Done in Jira and "
                "GA was announced by Marketing, but SRE globally set analytics_v2=FALSE "
                "due to DB connection pool exhaustion. Operational status: PAUSED."
            )
        return (
            "Analytics v2 has a critical discrepancy: Jira=Done, Marketing=GA, "
            "but production flag is FALSE (SRE rollback)."
        )
    elif any(k in query_lower for k in ["acme", "billing", "discount", "invoice"]):
        return (
            "Per Acme Corp Billing IMM: VP Marcus authorized a 35% discount override on Slack, "
            "but Jira BI-402 is still in To Do at standard $10,000/month. "
            "Customer has escalated invoice discrepancy. Action: update billing to $6,500/month."
        )
    elif any(k in query_lower for k in ["conflict", "discrepancy", "contradiction"]):
        return (
            "2 active contradictions:\n"
            "1. CON-001 [CRITICAL]: Analytics v2 GA announcement vs disabled production flag.\n"
            "2. CON-002 [HIGH]: Acme Corp Slack discount override vs unconfigured billing system."
        )
    return (
        "Operational state summary:\n"
        "  analytics_v2: flag=FALSE, status=PAUSED\n"
        "  acme_corp_billing: discount=35%, invoice=$10,000 (pending update), status=DISCREPANCY"
    )
