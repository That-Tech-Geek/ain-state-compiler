"""
Auto-Debugger Middle-End
Intercepts SchemaViolationErrors and dynamically patches the state
using a local LLM before resuming the pipeline.
"""
import json
import traceback
from typing import Dict, Any

from ain_state_compiler.compiler.reflection import ReflectionLog

try:
    import ollama
except ImportError:
    ollama = None

class AutoDebugger:
    def __init__(self, project_dir: str, model: str = "gemma3:1b"):
        self.project_dir = project_dir
        self.model = model
        self.reflection = ReflectionLog(project_dir)

    def is_available(self) -> bool:
        return ollama is not None

    def patch_schema(self, raw_input: Dict[str, Any], expected_schema: str, error_msg: str) -> Dict[str, Any]:
        """
        Attempts to use the local LLM to fix malformed input data to fit the schema.
        """
        # Log the crash
        self.reflection.log_failure(
            error_type="SchemaViolationError",
            raw_input=raw_input,
            expected_schema=expected_schema,
            stack_trace=traceback.format_exc()
        )

        if not self.is_available():
            raise Exception(f"Schema auto-patching failed: ollama is not installed. Original error: {error_msg}")

        prompt = (
            "You are an expert compiler debugger. A data parsing pipeline crashed due to a schema violation.\n"
            f"Expected Schema Details:\n{expected_schema}\n\n"
            f"Error Message: {error_msg}\n\n"
            f"Raw Input Data:\n{json.dumps(raw_input, indent=2)}\n\n"
            "Your task: Return a pure JSON object containing the sanitized/fixed data that conforms to the expected schema. "
            "Do not output markdown blocks or explanations, just raw JSON data. Infer missing fields gracefully."
        )

        try:
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            llm_text = response["message"]["content"].strip()
            
            # Remove markdown JSON wrappers if the model ignores the instruction
            if llm_text.startswith("```json"):
                llm_text = llm_text[7:]
            elif llm_text.startswith("```"):
                llm_text = llm_text[3:]
            if llm_text.endswith("```"):
                llm_text = llm_text[:-3]
            
            patched_data = json.loads(llm_text.strip())
            
            # Log the successful patch
            self.reflection.log_patch(
                raw_input=raw_input,
                patched_data=patched_data,
                model_used=self.model
            )
            
            return patched_data

        except Exception as e:
            raise Exception(f"Auto-debugger failed to patch data: {str(e)} -> Original error: {error_msg}")
