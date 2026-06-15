# AIN State Compiler

The **G-Brain Company Brain Primitive**: continuously compiles Slack, Jira, and Gmail into an executable, conflict-resolved operational state for AI agents.

## Overview

The `ain-state-compiler` operates 100% offline at the source level, parsing and aggregating enterprise communication and issue-tracking streams to produce internally consistent state representations. It prevents AI agents from executing against stale, fragmented, or conflicting corporate knowledge.

With the release of **v1.0.0**, `ain-state-compiler` graduates to an enterprise-grade agentic framework by incorporating industry-standard paradigms:
- **LangGraph-style Explicit Conflict Reducers** and Human-in-the-Loop interventions.
- **LlamaIndex-style Structured Data Extraction** using typed schemas.
- **MemGPT/Letta-style Core Memory Editing Tools** for long-term agent state persistence.

---

## 🚀 Installation

```bash
pip install ain-state-compiler
```

Ensure that you have Python 3.9+ installed. For the MCP and Ollama integrations, you must have the respective local dependencies running.

---

## 🛠️ Detailed Execution & Usage Guide

We provide multiple interfaces depending on your exact integration needs.

### 1. Model Context Protocol (MCP) Server
**Target Audience**: Claude Desktop, Cursor, Codex users.

The `ain-state-compiler` natively exposes the Model Context Protocol via `FastMCP`. Instead of copying and pasting internal slack logs into your agent window, just mount the MCP server!

**How to Start the Server:**
```bash
python -m ain_state_compiler.mcp_server
```

**Claude Desktop Configuration (`claude_desktop_config.json`):**
```json
{
  "mcpServers": {
    "ain-brain": {
      "command": "python",
      "args": ["-m", "ain_state_compiler.mcp_server"]
    }
  }
}
```

**Available Tools:**
- `search_ain_context(query_text: str, limit: int)`: BM25 Semantic Search for unstructured questions (e.g. "Why did the analytics migration fail?").
- `search_ain_by_tag(tag: str, limit: int)`: Exact O(1) matching for specific entities (e.g. "acme_billing").
- `edit_core_memory_replace(key: str, value: str)`: MemGPT-style tool to rewrite agent instructions and persona.
- `edit_core_memory_append(key: str, value: str)`: MemGPT-style tool to maintain long-term internal monologue over weeks or months.

### 2. Native Ollama Integration
**Target Audience**: Local LLM Developers.

If you are running `ollama` locally, you can route queries securely through native tool-calling pipelines.

**Usage:**
```python
from ain_state_compiler.ollama_plugin import run_query_with_tools

# The plugin will automatically invoke `search_context` tools behind the scenes!
answer = run_query_with_tools("What did Sara say about the latency spike?", model="gemma3:1b")
print(answer)
```

### 3. Command Line Interface (CLI)
**Target Audience**: DevOps & CI/CD Pipelines.

The CLI allows you to trigger syncing, ingestion, and offline queries.

**Initialize the Internal Database:**
```bash
ain-brain init-db
```

**Ingest from Sources (LlamaIndex-style Typed Extraction):**
(Pulls from your configured Jira, Slack, and Email APIs, mapping them directly into Pydantic-style Python dataclasses).
```bash
ain-brain ingest
```

**Sync with Human-in-the-Loop Reducers:**
(Runs a one-shot compilation and pauses if LangGraph-style heuristic reducers cannot automatically resolve a conflicting state).
```bash
ain-brain sync --human-in-the-loop
```

**Run a Query:**
(This invokes the Ollama tool-calling pipeline if running, or falls back to deterministic resolvers).
```bash
ain-brain query "analytics latency"
```

### 4. Python SDK Usage
**Target Audience**: Backend Engineers building custom agent frameworks.

```python
from ain_state_compiler.compiler import StateCompiler
from ain_state_compiler.retrieval import search_context

# 1. Compile state and detect conflicts
compiler = StateCompiler(project_dir="/path/to/project")
summary = compiler.compile()
print(f"Detected {summary['detected_conflicts']} active state conflicts.")

# 2. Programmatically Retrieve specific snippets
results = search_context("analytics_v2", limit=3, project_dir="/path/to/project")
for snippet in results:
    print(snippet)
```

---

## 🧠 Core Architecture

### "Ponytail" Lazy Gatekeepers
Internalizes the spirit of the "lazy senior dev" reductionist mindset directly into the core architecture:
- **LazyStateFilter**: A strict deterministic "No-Op" filter that drops incoming data if it does not meaningfully mutate the operational state.
- **StateReuseEngine**: Scans a historical cache of previously resolved conflicts. If a highly similar transformation exists, the compiler clones and adapts rather than generating from scratch.
- **StateCompilerEngine**: Enforces rigid bounds (`max_tokens`, length limits) on LLM compilation passes, aborting cleanly to naive primitives if structural code bloat occurs.

### Conflict Detection & LangGraph Reducers
- **ConflictDetector**: Runs rule-based, deterministic logic to spot discrepancies before invoking generation.
- **ReducerRegistry**: Define custom Python functions to merge conflicts programmatically. If no reducer matches, falls back to an optional `--human-in-the-loop` prompt.
- **TokenOptimizer**: Compresses verbose JSON state outputs into highly dense YAML representations, minimizing token footprint.

### Data Loaders & Schemas (LlamaIndex Paradigm)
- **DataLoaders**: Unstructured inputs are instantly mapped into structured `DocumentNode` schemas (e.g. `SlackMessageNode`, `JiraIssueNode`).

### Virtual Memory (MemGPT Paradigm)
- **CoreMemory**: Provides explicit CRUD tools allowing the agent LLM to self-edit its own prompt context indefinitely, surviving reboots and cache clears.

---

## Changelog

### v1.0.0 (Current)
- **LangGraph Reducers**: Introduced `ReducerRegistry` to programmatically resolve state merge conflicts.
- **Human in the Loop**: Added `--human-in-the-loop` to `ain-brain sync` CLI command.
- **LlamaIndex Schemas**: Introduced `ain_state_compiler.ingest.loaders.DataLoader` to enforce Pydantic-like dataclass typing on ingest streams.
- **Letta/MemGPT Core Memory**: Introduced `ain_state_compiler.core_memory.CoreMemory` and exposed explicit `edit_core_memory` self-editing tools to MCP and Ollama pipelines.

### v0.9.2
- **Extensive Documentation**: Added detailed execution guides for MCP Servers, Ollama Tooling, and CLI usage directly to the PyPI page. Fixed Windows emoji encoding bugs during packaging.

### v0.9.0
- **LLM-Native Retrieval Revamp**: Shifted away from raw Markdown context dumps to token-efficient Retrieval-Augmented Generation (RAG).
- **FTS5 Fast Search**: Extracted tight, context-rich snippets (truncated to scale) instead of unbounded document loads.
- **MCP Server**: Added `mcp_server.py` using `FastMCP` exposing `search_ain_context` and `search_ain_by_tag` to tools like Claude Desktop and Codex.
- **Native Ollama Tools**: Added `ollama_plugin.py` to route local queries securely through tool-calling pipelines.

### v0.8.3
- **Rebranding**: Updated GitHub URLs and package author metadata to That-Tech-Geek.

### v0.8.1
- **Ponytail Architecture**: Introduced programmatic gatekeepers.
- **State Minimization**: Implemented deterministic noise filtering.
