class LazyStateFilter:
    """Drops incoming data if it doesn't change the operational state."""
    @staticmethod
    def is_state_mutation_required(incoming_payload: dict, current_state: dict) -> bool:
        # 1. Deterministic noise filtering (e.g., automated system notifications, 'thanks' messages)
        if incoming_payload.get("type") == "chatter":
            return False
            
        # 2. Key-value semantic hash comparison 
        # If an identical operational conflict/state value was resolved within a threshold, skip.
        if current_state.get(incoming_payload.get("id")) == incoming_payload.get("status"):
            return False
            
        return True

class StateReuseEngine:
    """Enforces the 'Don't Repeat Yourself' principle at the compiler level."""
    def __init__(self, historical_state_cache: list):
        # In a real implementation this would be a Vector index or simple match tree
        self.cache = historical_state_cache 
        
    def find_reusable_primitive(self, compilation_intent: str) -> dict | None:
        # Match current intent against previous executable state trees
        if hasattr(self.cache, 'search'):
            match = self.cache.search(compilation_intent, threshold=0.92)
            if match:
                # Return the pre-existing primitive to bypass generative code bloat entirely
                return match.compiled_state_node 
        return None

class StateCompilerEngine:
    """A wrapper engine that applies rigid metric limits to LLM compilations."""
    
    def __init__(self):
        # Stub for the fallback primitive
        pass
        
    def fallback_to_naive_primitive(self, payload: dict) -> str:
        return "{'status': 'error', 'message': 'Compilation aborted due to complexity bloat.'}"

    def llm_call(self, prompt: dict, temperature: float, max_tokens: int) -> str:
        # Stub for an LLM call; in reality, this calls Ollama or another LLM
        return "{'compiled': 'true'}"

    def compile_payload_to_state(self, payload: dict) -> str:
        # Low temperature keeps the model concise and deterministic
        # Aggressive max_tokens acts as a physical boundary against structural bloat
        compiled_output = self.llm_call(
            prompt=payload, 
            temperature=0.1, 
            max_tokens=150 
        )
        
        # Self-Correction Guard: The compiler fails if the code footprint is too massive
        if len(compiled_output.split("\n")) > 10:
            return self.fallback_to_naive_primitive(payload)
            
        return compiled_output
