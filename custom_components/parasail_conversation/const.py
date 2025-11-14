"""Constants for the Parasail Conversation integration."""

DOMAIN = "parasail_conversation"

CONF_API_KEY = "api_key"
CONF_MODEL = "model"
CONF_TEMPERATURE = "temperature"
CONF_MAX_TOKENS = "max_tokens"
CONF_TOP_P = "top_p"

DEFAULT_MODEL = "parasail-qwen3-32b"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TOP_P = 1.0

PARASAIL_API_BASE = "https://api.parasail.ai/v1"

# Available Parasail models
PARASAIL_MODELS = [
    "parasail-llama-33-70b-fp8",
    "parasail-llama-4-scout-instruct",
    "parasail-llama-4-maverick-instruct-fp8",
    "parasail-qwen3-30b-a3b",
    "parasail-qwen3-235b-a22b",
    "parasail-qwen3-32b",
    "parasail-gemma3-27b-it",
    "parasail-mistral-devstral-small",
]
