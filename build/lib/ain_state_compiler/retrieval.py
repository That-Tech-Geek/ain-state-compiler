"""
Retrieval Module for AIN State Compiler

Provides token-efficient search methods tailored for LLM tool invocation.
It interfaces directly with the ContextIndexer's SQLite FTS5 database to 
return tightly formatted text snippets instead of raw JSON or giant markdown blobs.
"""

import os
from datetime import datetime

def _find_project_dir():
    """Finds the root project directory containing context_index.db or mock_data."""
    cwd = os.getcwd()
    for candidate in [cwd] + [os.path.dirname(cwd)] * 4:
        if os.path.isdir(os.path.join(candidate, "mock_data")) or \
           os.path.isdir(os.path.join(candidate, "compiled_state")) or \
           os.path.exists(os.path.join(candidate, "context_index.db")):
            return candidate
    return cwd

def _format_snippets(results):
    """
    Takes raw FTS5 search results and formats them into a token-efficient string.
    Removes heavy JSON bloat.
    """
    if not results:
        return "No relevant context found."
    
    formatted = []
    for r in results:
        ts = r.get("timestamp") or "unknown time"
        src = r.get("source") or "unknown"
        author = r.get("author") or "unknown"
        subj = r.get("subject") or ""
        body = r.get("body") or ""
        
        snippet = f"[{ts}] {src.upper()} | {author}"
        if subj:
            snippet += f"\nSubject: {subj}"
        if body:
            # truncate excessively long body text to save tokens
            snippet += f"\nBody: {body[:1500]}..." if len(body) > 1500 else f"\nBody: {body}"
            
        formatted.append(snippet)
        
    return "\n---\n".join(formatted)


def search_context(query_text: str, limit: int = 5, project_dir: str = None) -> str:
    """
    Search the AIN Company Brain using semantic keywords.
    
    Args:
        query_text: Space-separated keywords to search for.
        limit: Max number of snippets to return.
    
    Returns:
        A formatted string of relevant snippets for the LLM.
    """
    from ain_state_compiler.ingest.indexer import ContextIndexer
    
    if not project_dir:
        project_dir = _find_project_dir()
        
    idx = ContextIndexer(project_dir)
    try:
        if not os.path.exists(idx.db_path):
            return "Context index database not found. Has ingestion been run?"
            
        results = idx.search(query_text, limit=limit)
        return _format_snippets(results)
    finally:
        idx.close()


def search_by_tag(tag: str, limit: int = 5, project_dir: str = None) -> str:
    """
    Search the AIN Company Brain using exact topic tags.
    
    Args:
        tag: An exact tag/keyword (e.g., 'analytics', 'acme').
        limit: Max number of snippets to return.
        
    Returns:
        A formatted string of relevant snippets for the LLM.
    """
    from ain_state_compiler.ingest.indexer import ContextIndexer
    
    if not project_dir:
        project_dir = _find_project_dir()
        
    idx = ContextIndexer(project_dir)
    try:
        if not os.path.exists(idx.db_path):
            return "Context index database not found. Has ingestion been run?"
            
        results = idx.search_by_tag(tag, limit=limit)
        return _format_snippets(results)
    finally:
        idx.close()
