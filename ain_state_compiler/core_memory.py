"""
Letta/MemGPT-Style Core Memory Block
Implements a VirtualMemory system where agents can continuously edit
their own operational instructions or "Internal Monologue".
"""
import os
import json

class CoreMemory:
    """
    Manages the 'Main Context' block of agent memory.
    This is analogous to MemGPT's 'core memory'.
    Stored locally in `core_memory.json`.
    """
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.memory_file = os.path.join(project_dir, "core_memory.json")
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.memory_file):
            default_mem = {
                "persona": "You are a senior orchestration agent managing AIN State.",
                "human_operator": "The user is an engineering manager. Be concise.",
                "current_task": "Awaiting instructions."
            }
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(default_mem, f, indent=2)

    def read_memory(self) -> dict:
        self._ensure_file()
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def core_memory_replace(self, key: str, value: str) -> bool:
        """Explicit tool to overwrite a memory block."""
        mem = self.read_memory()
        mem[key] = value
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(mem, f, indent=2)
        return True

    def core_memory_append(self, key: str, value: str) -> bool:
        """Explicit tool to append to a memory block."""
        mem = self.read_memory()
        existing = mem.get(key, "")
        mem[key] = existing + "\n" + value if existing else value
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(mem, f, indent=2)
        return True

    def get_prompt_context(self) -> str:
        """Formats the core memory into a system prompt injection."""
        mem = self.read_memory()
        lines = ["--- CORE MEMORY ---"]
        for k, v in mem.items():
            lines.append(f"[{k.upper()}]:\n{v}\n")
        lines.append("-------------------")
        return "\n".join(lines)
