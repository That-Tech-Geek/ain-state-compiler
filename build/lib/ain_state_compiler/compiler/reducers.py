"""
LangGraph-Style State Reducers
Allows developers to programmatically define how cross-domain state merges occur
when handling conflicting updates.
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List

@dataclass
class StateConflict:
    id: str
    category: str
    title: str
    severity: str
    summary: str
    evidence: List[Dict[str, str]]
    resolved: bool = False
    resolution_action: str = ""

class ReducerRegistry:
    def __init__(self):
        self._reducers: Dict[str, Callable[[StateConflict], Any]] = {}

    def register(self, category: str, reducer_func: Callable[[StateConflict], Any]):
        """Registers a custom Python reducer function for a specific conflict category."""
        self._reducers[category] = reducer_func

    def reduce(self, conflict: StateConflict, human_in_the_loop: bool = False) -> StateConflict:
        # 1. Attempt programmatic reduction
        if conflict.category in self._reducers:
            resolution = self._reducers[conflict.category](conflict)
            if resolution:
                conflict.resolved = True
                conflict.resolution_action = f"Auto-merged via reducer: {resolution}"
                return conflict
        
        # 2. Human-in-the-loop fallback
        if human_in_the_loop and not conflict.resolved:
            print(f"\n[HUMAN-IN-THE-LOOP] Unresolved Conflict: {conflict.id} - {conflict.category}")
            print(f"Summary: {conflict.summary}")
            print("Evidence:")
            for ev in conflict.evidence:
                print(f" - {ev['source']}: {ev['assertion']}")
            choice = input("Enter resolution instruction (or 'skip' to leave unresolved): ")
            if choice.strip().lower() != 'skip':
                conflict.resolved = True
                conflict.resolution_action = f"Human override: {choice}"
                
        return conflict

# Global default registry
default_registry = ReducerRegistry()

# Example default reducer for BILLING conflicts
def billing_reducer(conflict: StateConflict) -> str:
    # E.g. If VP override exists, VP wins.
    for ev in conflict.evidence:
        if "VP" in ev['assertion'] and "override" in ev['assertion'].lower():
            return "VP Override takes precedence over Jira status."
    return ""

default_registry.register("BILLING", billing_reducer)
