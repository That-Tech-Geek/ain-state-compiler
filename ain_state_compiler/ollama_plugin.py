"""
Ollama Plugin Wrapper for AIN State Compiler Retrieval

Exposes the token-efficient retrieval module as native tools for local Ollama models.
"""

import os
from ain_state_compiler.retrieval import search_context, search_by_tag

try:
    import ollama
except ImportError:
    ollama = None


def is_ollama_available():
    return ollama is not None


def run_query_with_tools(query_text: str, model: str = "gemma3:1b"):
    """
    Run a query against Ollama, providing it the search_context and search_by_tag tools.
    The LLM will iteratively use these tools to fetch data before responding.
    """
    if not is_ollama_available():
        return "Error: The 'ollama' python package is not installed."

    messages = [
        {
            "role": "system",
            "content": (
                "You are the AIN Company Brain assistant. You have access to tools that can search the "
                "company's internal communications (Slack, Jira, Email). "
                "If the user asks a specific question about the company, ALWAYS use `search_context` "
                "or `search_by_tag` to look up the answer. Do not guess."
            )
        },
        {
            "role": "user",
            "content": query_text
        }
    ]

    available_functions = {
        "search_context": search_context,
        "search_by_tag": search_by_tag
    }

    try:
        # Step 1: Send query to LLM with tool definitions
        response = ollama.chat(
            model=model,
            messages=messages,
            tools=[search_context, search_by_tag]
        )

        messages.append(response["message"])

        # Step 2: If LLM requested tool execution, run them
        if response["message"].get("tool_calls"):
            for tool_call in response["message"]["tool_calls"]:
                function_name = tool_call["function"]["name"]
                arguments = tool_call["function"]["arguments"]

                if function_name in available_functions:
                    function_to_call = available_functions[function_name]
                    # Execute tool
                    tool_output = function_to_call(**arguments)
                    
                    # Append tool response back to the conversation
                    messages.append({
                        "role": "tool",
                        "content": tool_output,
                        "name": function_name
                    })

            # Step 3: LLM generates final answer based on the tool outputs
            final_response = ollama.chat(model=model, messages=messages)
            return final_response["message"]["content"]
            
        else:
            return response["message"]["content"]

    except Exception as e:
        return f"Error communicating with Ollama: {str(e)}"

