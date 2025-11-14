"""Utility functions for Parasail Conversation."""
from __future__ import annotations

import json
from typing import Any


def fix_llm_tool_args(args: dict[str, Any]) -> dict[str, Any]:
    """Fix common LLM mistakes in tool arguments.

    LLMs sometimes send JSON arrays as strings, e.g.:
    - '["Family Room"]' instead of "Family Room" or ["Family Room"]
    - Trailing spaces in names
    """
    fixed_args = {}

    for key, value in args.items():
        if isinstance(value, str):
            # Check if it's a JSON array string
            if value.startswith('[') and value.endswith(']'):
                try:
                    # Parse the JSON array string
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        # If single item, unwrap it to a string
                        if len(parsed) == 1:
                            fixed_args[key] = parsed[0].strip() if isinstance(parsed[0], str) else parsed[0]
                        else:
                            # Multiple items - keep as array but strip strings
                            fixed_args[key] = [item.strip() if isinstance(item, str) else item for item in parsed]
                    else:
                        fixed_args[key] = value
                except (json.JSONDecodeError, ValueError):
                    # Not valid JSON, keep original
                    fixed_args[key] = value
            else:
                # Regular string, just strip whitespace
                fixed_args[key] = value.strip()
        else:
            # Not a string, keep as-is
            fixed_args[key] = value

    return fixed_args
