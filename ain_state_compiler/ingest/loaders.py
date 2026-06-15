"""
LlamaIndex-Style Data Loaders & Schemas
Enforces strict typing on ingested logs using dataclasses, mimicking Pydantic.
Extracts structured information from unstructured text streams.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Any
from datetime import datetime

@dataclass
class DocumentNode:
    """Base node for ingested data, akin to LlamaIndex's Document or Node."""
    id: str
    source_type: str
    text_content: str
    metadata: dict = field(default_factory=dict)
    timestamp: str = ""

@dataclass
class SlackMessageNode(DocumentNode):
    channel: str = ""
    user: str = ""
    is_reply: bool = False

@dataclass
class JiraIssueNode(DocumentNode):
    status: str = ""
    assignee: str = ""
    priority: str = ""

@dataclass
class EmailNode(DocumentNode):
    subject: str = ""
    sender: str = ""
    recipients: List[str] = field(default_factory=list)

class SchemaViolationError(Exception):
    pass

class DataLoader:
    """Transforms raw dictionaries into typed schema nodes."""
    
    def __init__(self, project_dir: str):
        from ain_state_compiler.compiler.auto_debugger import AutoDebugger
        self.debugger = AutoDebugger(project_dir)

    def parse_slack(self, raw_list: List[dict]) -> List[SlackMessageNode]:
        nodes = []
        schema_def = "SlackMessageNode(channel: str, user: str, is_reply: bool, text_content: str, timestamp: str)"
        for r in raw_list:
            try:
                # Deliberate strict validation: timestamp is required and must not be empty
                ts = r.get("ts", r.get("timestamp", ""))
                if not ts:
                    raise SchemaViolationError("Missing required field: timestamp")
                    
                node = SlackMessageNode(
                    id=f"slack-{r.get('channel', 'unknown')}-{ts}",
                    source_type="slack",
                    text_content=r.get("text", ""),
                    timestamp=ts,
                    channel=r.get("channel", ""),
                    user=r.get("user", ""),
                    is_reply=bool(r.get("thread_ts")),
                    metadata=r
                )
                nodes.append(node)
            except Exception as e:
                try:
                    fixed_data = self.debugger.patch_schema(r, schema_def, str(e))
                    # Retry with patched data
                    ts = fixed_data.get("ts", fixed_data.get("timestamp", str(datetime.now().timestamp())))
                    node = SlackMessageNode(
                        id=f"slack-{fixed_data.get('channel', 'unknown')}-{ts}",
                        source_type="slack",
                        text_content=fixed_data.get("text", fixed_data.get("text_content", "")),
                        timestamp=ts,
                        channel=fixed_data.get("channel", ""),
                        user=fixed_data.get("user", ""),
                        is_reply=bool(fixed_data.get("thread_ts") or fixed_data.get("is_reply")),
                        metadata=fixed_data
                    )
                    nodes.append(node)
                except Exception as patch_e:
                    print(f"[!] Dropping Slack node. Auto-debugger failed: {patch_e}")
                    
        return nodes

    def parse_jira(self, raw_list: List[dict]) -> List[JiraIssueNode]:
        nodes = []
        schema_def = "JiraIssueNode(id: str, status: str, assignee: str, priority: str, text_content: str, timestamp: str)"
        for r in raw_list:
            try:
                id_val = r.get("id", "")
                if not id_val:
                    raise SchemaViolationError("Missing required field: id")
                node = JiraIssueNode(
                    id=id_val,
                    source_type="jira",
                    text_content=r.get("description", "") + "\n" + r.get("title", ""),
                    timestamp=r.get("updated", r.get("updated_at", "")),
                    status=r.get("status", ""),
                    assignee=r.get("assignee", ""),
                    priority=r.get("priority", ""),
                    metadata=r
                )
                nodes.append(node)
            except Exception as e:
                try:
                    fixed_data = self.debugger.patch_schema(r, schema_def, str(e))
                    node = JiraIssueNode(
                        id=fixed_data.get("id", "UNKNOWN"),
                        source_type="jira",
                        text_content=fixed_data.get("description", "") + "\n" + fixed_data.get("title", ""),
                        timestamp=fixed_data.get("updated", fixed_data.get("updated_at", str(datetime.now().timestamp()))),
                        status=fixed_data.get("status", ""),
                        assignee=fixed_data.get("assignee", ""),
                        priority=fixed_data.get("priority", ""),
                        metadata=fixed_data
                    )
                    nodes.append(node)
                except Exception as patch_e:
                    print(f"[!] Dropping Jira node. Auto-debugger failed: {patch_e}")
        return nodes

    def parse_email(self, raw_list: List[dict]) -> List[EmailNode]:
        nodes = []
        schema_def = "EmailNode(id: str, subject: str, sender: str, recipients: List[str], text_content: str, timestamp: str)"
        for r in raw_list:
            try:
                id_val = r.get("id", "")
                if not id_val:
                    raise SchemaViolationError("Missing required field: id")
                node = EmailNode(
                    id=id_val,
                    source_type="email",
                    text_content=r.get("body", ""),
                    timestamp=r.get("date", r.get("timestamp", "")),
                    subject=r.get("subject", ""),
                    sender=r.get("sender", ""),
                    recipients=r.get("recipients", "").split(",") if isinstance(r.get("recipients"), str) else r.get("recipients", []),
                    metadata=r
                )
                nodes.append(node)
            except Exception as e:
                try:
                    fixed_data = self.debugger.patch_schema(r, schema_def, str(e))
                    recs = fixed_data.get("recipients", [])
                    if isinstance(recs, str):
                        recs = recs.split(",")
                    node = EmailNode(
                        id=fixed_data.get("id", "UNKNOWN"),
                        source_type="email",
                        text_content=fixed_data.get("body", fixed_data.get("text_content", "")),
                        timestamp=fixed_data.get("date", fixed_data.get("timestamp", str(datetime.now().timestamp()))),
                        subject=fixed_data.get("subject", ""),
                        sender=fixed_data.get("sender", ""),
                        recipients=recs,
                        metadata=fixed_data
                    )
                    nodes.append(node)
                except Exception as patch_e:
                    print(f"[!] Dropping Email node. Auto-debugger failed: {patch_e}")
        return nodes
