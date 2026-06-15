"""
Local Reflection Log System
Captures telemetry for auto-debugging completely offline.
No cloud telemetry, metrics, or traces leave the local machine.
"""

import os
import json
from datetime import datetime

class ReflectionLog:
    """Manages local logging of AST crashes and LLM auto-patches."""
    
    def __init__(self, project_dir):
        self.log_file = os.path.join(project_dir, "reflection_log.json")

    def _load(self):
        if not os.path.exists(self.log_file):
            return []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def log_failure(self, error_type: str, raw_input: dict, expected_schema: str, stack_trace: str):
        """Logs an interception of a schema or reducer crash."""
        logs = self._load()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "CRASH_INTERCEPTED",
            "error_type": error_type,
            "raw_input": raw_input,
            "expected_schema": expected_schema,
            "stack_trace": stack_trace,
            "patched": False
        }
        logs.append(entry)
        self._write(logs)

    def log_patch(self, raw_input: dict, patched_data: dict, model_used: str):
        """Logs the successful inline correction from the LLM."""
        logs = self._load()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "AUTO_PATCH_APPLIED",
            "model_used": model_used,
            "raw_input": raw_input,
            "patched_data": patched_data
        }
        logs.append(entry)
        self._write(logs)

    def _write(self, logs):
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)
