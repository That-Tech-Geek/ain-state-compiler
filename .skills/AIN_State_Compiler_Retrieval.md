---
name: AIN_State_Compiler_Retrieval
description: Protocols for querying the AIN State Compiler using MCP tools or Ollama plugin.
---

# AIN State Compiler Retrieval Protocol

You are interacting with the AIN State Compiler's highly-optimized retrieval system. This system allows you to search across Slack, Jira, and Email records securely without blowing up your context window.

## Available Tools

The MCP Server (or Ollama Plugin) exposes two primary tools:

1. **`search_ain_context(query_text: str, limit: int = 5)`**
   - **When to use**: Broad, semantic questions (e.g. "Why is analytics v2 throwing exceptions?" or "What did Marcus say about the Acme discount?").
   - **Behavior**: Uses an FTS5 BM25 search index. Provide standard search engine keywords rather than full sentences for best results.

2. **`search_ain_by_tag(tag: str, limit: int = 5)`**
   - **When to use**: Looking for an exact topic, person, or known entity (e.g. "acme", "analytics", "sara_devops").
   - **Behavior**: Uses an inverted tag index for fast O(1) matching.

## Execution Rules

- **DO NOT** guess the operational state. If a user asks a question about the project state, team communications, or Jira issues, **ALWAYS** call the retrieval tools first.
- **DO NOT** request high limits unless necessary. A limit of 5-10 is sufficient to gather the needed facts while conserving tokens.
- **Iterative Search**: If the first query yields "No relevant context found" or unrelated results, refine your keywords and try again before giving up.
- **Interpret Snippets Correctly**: The tools return snippets formatted as `[timestamp] SOURCE | author`. Use this provenance to provide accurate citations to the user (e.g. "According to a Slack message by Alex at 09:15...").

## Example Workflow

User: "What is the status of the Acme Corp billing?"
1. Call `search_ain_by_tag(tag="acme", limit=3)`
2. Call `search_ain_context(query_text="acme billing discount invoice", limit=5)`
3. Synthesize the snippets into a cohesive response.
