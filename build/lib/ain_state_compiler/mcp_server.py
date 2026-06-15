"""
MCP Server for AIN State Compiler

Exposes the token-efficient retrieval logic to MCP-compatible clients like Claude Desktop, Cursor, and Codex.
Run this script directly to start the stdio server.
"""

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError("The 'mcp' python package is required to run the MCP server. Install it with `pip install mcp`.")

import os
from ain_state_compiler.retrieval import search_context, search_by_tag
from ain_state_compiler.core_memory import CoreMemory

# Create an MCP server
mcp = FastMCP("AIN State Compiler Retrieval")

@mcp.tool()
def search_ain_context(query_text: str, limit: int = 5) -> str:
    """
    Search the AIN Company Brain using semantic keywords.
    Use this tool when you need to answer questions about the company's internal communications (Slack, Jira, Emails).
    
    Args:
        query_text: The search terms (e.g. "analytics rollout latency")
        limit: Max number of results to return
    """
    return search_context(query_text, limit=limit)

@mcp.tool()
def search_ain_by_tag(tag: str, limit: int = 5) -> str:
    """
    Search the AIN Company Brain using exact topic tags.
    Use this tool when looking up a specific ID, tag, or topic (e.g. 'analytics', 'acme_corp').
    
    Args:
        tag: The exact tag to search for
        limit: Max number of results to return
    """
    return search_by_tag(tag, limit=limit)

@mcp.tool()
def edit_core_memory_replace(key: str, value: str) -> str:
    """
    Overwrites a core memory block entirely (MemGPT-style).
    Use this to replace your instructions or persona.
    
    Args:
        key: The memory block key (e.g. 'persona', 'current_task')
        value: The new content
    """
    mem = CoreMemory(os.getcwd())
    mem.core_memory_replace(key, value)
    return f"Successfully replaced core memory block '{key}'."

@mcp.tool()
def edit_core_memory_append(key: str, value: str) -> str:
    """
    Appends text to a core memory block (MemGPT-style).
    Use this to add a new task or note to your internal monologue.
    
    Args:
        key: The memory block key (e.g. 'current_task')
        value: The content to append
    """
    mem = CoreMemory(os.getcwd())
    mem.core_memory_append(key, value)
    return f"Successfully appended to core memory block '{key}'."

if __name__ == "__main__":
    # Start the server using standard input/output (the default MCP transport)
    mcp.run()
