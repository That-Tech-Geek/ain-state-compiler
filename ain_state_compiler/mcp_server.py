"""
MCP Server for AIN State Compiler

Exposes the token-efficient retrieval logic to MCP-compatible clients like Claude Desktop, Cursor, and Codex.
Run this script directly to start the stdio server.
"""

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError("The 'mcp' python package is required to run the MCP server. Install it with `pip install mcp`.")

from ain_state_compiler.retrieval import search_context, search_by_tag

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

if __name__ == "__main__":
    # Start the server using standard input/output (the default MCP transport)
    mcp.run()
