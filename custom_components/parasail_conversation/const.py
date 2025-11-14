"""Constants for the Parasail Conversation integration."""

DOMAIN = "parasail_conversation"

CONF_API_KEY = "api_key"
CONF_MODEL = "model"
CONF_TEMPERATURE = "temperature"
CONF_MAX_TOKENS = "max_tokens"
CONF_TOP_P = "top_p"
CONF_LLM_HASS_API = "llm_hass_api"
CONF_PROMPT = "prompt"

DEFAULT_MODEL = "parasail-qwen3-32b"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TOP_P = 1.0
DEFAULT_PROMPT = """You are a helpful voice assistant for Home Assistant. Your role is to help control smart home devices and answer questions about the home.

When controlling devices:
- Be precise and confirm actions
- Use the available tools to control devices
- If you're unsure about a device name, ask for clarification

Keep responses concise and natural."""

PARASAIL_API_BASE = "https://api.parasail.io/v1"

# Available Parasail models
PARASAIL_MODELS = [
    "meta-llama/Llama-3.3-70B-Instruct",
]
