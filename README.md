# ain-state-compiler

The G-Brain Company Brain Primitive: continuously compiles Slack, Jira, and Gmail into an executable, conflict-resolved operational state for AI agents.

## Overview

The `ain-state-compiler` operates 100% offline at the source level, parsing and aggregating enterprise communication and issue-tracking streams to produce internally consistent state representations. It prevents AI agents from executing against stale, fragmented, or conflicting corporate knowledge.

### Key Outputs
- **Institutional Memory Modules (IMMs)**: Markdown-based, human- and machine-readable state snapshots.
- **Operational Execution Graphs (OEGs)**: Optimized YAML topologies representing resolution paths.
- **Active Conflict Reports**: Discrepancy matrices identifying contradictions between engineering, marketing, and support data.

## Installation

```bash
pip install ain-state-compiler
```

## Usage

```python
from ain_state_compiler.compiler import StateCompiler

# The project directory should contain a 'mock_data' folder with slack_history.json, jira_issues.json, and emails.json
compiler = StateCompiler(project_dir="/path/to/project")
summary = compiler.compile()

print(f"Processed {summary['processed_slack_events']} Slack events.")
print(f"Detected {summary['detected_conflicts']} active state conflicts.")
```

## Core Architecture

### "Ponytail" Lazy Gatekeepers
Internalizes the spirit of the "lazy senior dev" reductionist mindset directly into the core architecture:
- **LazyStateFilter**: A strict deterministic "No-Op" filter that drops incoming data if it does not meaningfully mutate the operational state.
- **StateReuseEngine**: Scans a historical cache of previously resolved conflicts. If a highly similar transformation exists, the compiler clones and adapts rather than generating from scratch.
- **StateCompilerEngine**: Enforces rigid bounds (`max_tokens`, length limits) on LLM compilation passes, aborting cleanly to naive primitives if structural code bloat occurs.

### Conflict Detection & Optimization
- **ConflictDetector**: Runs rule-based, deterministic logic to spot discrepancies before invoking generation.
- **TokenOptimizer**: Compresses verbose JSON state outputs into highly dense YAML representations, minimizing token footprint for downstream agent ingestion.

## Changelog

### v0.9.0 (Current)
- **LLM-Native Retrieval Revamp**: Shifted away from raw Markdown context dumps to token-efficient Retrieval-Augmented Generation (RAG).
- **FTS5 Fast Search**: Extracted tight, context-rich snippets (truncated to scale) instead of unbounded document loads.
- **MCP Server**: Added `mcp_server.py` using `FastMCP` exposing `search_ain_context` and `search_ain_by_tag` to tools like Claude Desktop and Codex.
- **Native Ollama Tools**: Added `ollama_plugin.py` to route local queries securely through tool-calling pipelines.

### v0.8.3
- **Rebranding**: Updated GitHub URLs and package author metadata to That-Tech-Geek.

### v0.8.1
- **Ponytail Architecture**: Introduced `LazyStateFilter`, `StateReuseEngine`, and `StateCompilerEngine` programmatic gatekeepers.
- **State Minimization**: Implemented deterministic noise filtering and semantic hash comparisons to prevent unnecessary compilation.
- **Token/Complexity Penalties**: Set rigid metric constraints for generative compilation steps to minimize complexity.
