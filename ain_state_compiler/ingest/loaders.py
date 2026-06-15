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

class DataLoader:
    """Transforms raw dictionaries into typed schema nodes."""
    
    @staticmethod
    def parse_slack(raw_list: List[dict]) -> List[SlackMessageNode]:
        nodes = []
        for r in raw_list:
            node = SlackMessageNode(
                id=f"slack-{r.get('channel', 'unknown')}-{r.get('ts', r.get('timestamp', ''))}",
                source_type="slack",
                text_content=r.get("text", ""),
                timestamp=r.get("ts", r.get("timestamp", "")),
                channel=r.get("channel", ""),
                user=r.get("user", ""),
                is_reply=bool(r.get("thread_ts")),
                metadata=r
            )
            nodes.append(node)
        return nodes

    @staticmethod
    def parse_jira(raw_list: List[dict]) -> List[JiraIssueNode]:
        nodes = []
        for r in raw_list:
            node = JiraIssueNode(
                id=r.get("id", ""),
                source_type="jira",
                text_content=r.get("description", "") + "\n" + r.get("title", ""),
                timestamp=r.get("updated", r.get("updated_at", "")),
                status=r.get("status", ""),
                assignee=r.get("assignee", ""),
                priority=r.get("priority", ""),
                metadata=r
            )
            nodes.append(node)
        return nodes

    @staticmethod
    def parse_email(raw_list: List[dict]) -> List[EmailNode]:
        nodes = []
        for r in raw_list:
            node = EmailNode(
                id=r.get("id", ""),
                source_type="email",
                text_content=r.get("body", ""),
                timestamp=r.get("date", r.get("timestamp", "")),
                subject=r.get("subject", ""),
                sender=r.get("sender", ""),
                recipients=r.get("recipients", "").split(",") if isinstance(r.get("recipients"), str) else r.get("recipients", []),
                metadata=r
            )
            nodes.append(node)
        return nodes
