"""
ain-state-compiler: The G-Brain Enterprise Company Brain Primitive.

A local-first, offline-ingestion engine that continuously compiles raw
corporate communications (Slack, Jira, Gmail) into an executable,
internally consistent operational state representation — ready for AI agents.

Zero-LLM at source. LLMs called only on-demand query.
"""

__version__ = "0.3.2"
__author__ = "Sambit Mishra"
__email__ = "contact@ain-compiler.ai"

from ain_state_compiler.compiler.state_compiler import StateCompiler
from ain_state_compiler.compiler.conflict_detector import ConflictDetector
from ain_state_compiler.compiler.token_optimizer import TokenOptimizer
from ain_state_compiler.ingest.indexer import ContextIndexer
from ain_state_compiler.ingest.orchestrator import orchestrate_ingest

__all__ = [
    "StateCompiler",
    "ConflictDetector",
    "TokenOptimizer",
    "ContextIndexer",
    "orchestrate_ingest",
    "__version__",
]
