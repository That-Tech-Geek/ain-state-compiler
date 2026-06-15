"""
Token Optimizer Module
Zero-dependency JSON-to-YAML converter that strips verbose JSON formatting
tokens (brackets, quotes, commas) to reduce prompt size by 15-30%.

No PyYAML, no external dependencies.
"""

import json


class TokenOptimizer:
    """
    Translates nested JSON structures into clean, bracket-less YAML.

    Corporate LLM prompts typically source their context from database
    JSON blobs. Stripping JSON syntax reduces token count 14-30%,
    lowering inference latency and API costs.
    """

    @staticmethod
    def json_to_yaml(data, indent=0):
        """
        Custom clean JSON-to-YAML compiler.
        Zero external dependencies -- pure Python loops.
        """
        lines = []
        spacing = " " * indent

        if isinstance(data, dict):
            for key, value in data.items():
                clean_key = str(key)
                if ":" in clean_key or " " in clean_key:
                    clean_key = f'"{clean_key}"'

                if isinstance(value, (dict, list)):
                    lines.append(f"{spacing}{clean_key}:")
                    lines.append(TokenOptimizer.json_to_yaml(value, indent + 2))
                else:
                    clean_val = str(value).replace("\n", " ").strip()
                    if clean_val.lower() in ["true", "false", "null", "yes", "no"]:
                        lines.append(f"{spacing}{clean_key}: {clean_val}")
                    elif any(c in clean_val for c in [":", "{", "}", "[", "]", ",", "#"]):
                        lines.append(f'{spacing}{clean_key}: "{clean_val}"')
                    else:
                        lines.append(f"{spacing}{clean_key}: {clean_val}")

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    sub_yaml = TokenOptimizer.json_to_yaml(item, indent + 2).lstrip()
                    lines.append(f"{spacing}- {sub_yaml}")
                else:
                    clean_val = str(item).replace("\n", " ").strip()
                    lines.append(f"{spacing}- {clean_val}")
        else:
            lines.append(f"{spacing}{data}")

        return "\n".join(lines)

    @staticmethod
    def calculate_savings(json_data):
        """
        Returns a metrics dict comparing JSON vs YAML character / token counts.
        Token approximation: 1 token = ~4 characters.
        """
        if isinstance(json_data, (dict, list)):
            json_str = json.dumps(json_data, indent=2)
            raw_data = json_data
        else:
            json_str = str(json_data)
            try:
                raw_data = json.loads(json_data)
            except Exception:
                raw_data = json_data

        yaml_str = TokenOptimizer.json_to_yaml(raw_data)

        json_chars = len(json_str)
        yaml_chars = len(yaml_str)

        json_tokens = max(1, round(json_chars / 4))
        yaml_tokens = max(1, round(yaml_chars / 4))

        saved_chars = json_chars - yaml_chars
        saved_tokens = json_tokens - yaml_tokens
        saving_percentage = (saved_chars / json_chars * 100) if json_chars > 0 else 0

        return {
            "json_characters": json_chars,
            "yaml_characters": yaml_chars,
            "json_tokens": json_tokens,
            "yaml_tokens": yaml_tokens,
            "saved_characters": saved_chars,
            "saved_tokens": saved_tokens,
            "saving_percentage": round(saving_percentage, 1),
            "yaml_output": yaml_str,
        }
