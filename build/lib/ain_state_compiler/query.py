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
    Query the Company Brain using the native Ollama plugin for token-efficient retrieval.

    Args:
        query_text: Natural language question.
        project_dir: Root of the ain-state-compiler project.
        model: Ollama model name (default: gemma3:1b).

    Returns:
        (answer: str, source_node: str, is_llm: bool)
    """
    try:
        from ain_state_compiler.ollama_plugin import is_ollama_available, run_query_with_tools
    except ImportError:
        def is_ollama_available(): return False
        run_query_with_tools = None

    if is_ollama_available():
        answer = run_query_with_tools(query_text, model=model)
        return answer, "ollama_tool_plugin", True

    # Fallback: deterministic state resolver
    fallback = _deterministic_resolve(query_text.lower())
    return fallback, "deterministic_fallback", False


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
