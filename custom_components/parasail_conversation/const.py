"""Constants for the Parasail Conversation integration."""

DOMAIN = "parasail_conversation"

CONF_API_KEY = "api_key"
CONF_BRAVE_API_KEY = "brave_api_key"
CONF_MODEL = "model"
CONF_TEMPERATURE = "temperature"
CONF_MAX_TOKENS = "max_tokens"
CONF_TOP_P = "top_p"
CONF_LLM_HASS_API = "llm_hass_api"
CONF_PROMPT = "prompt"

DEFAULT_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TOP_P = 1.0
DEFAULT_PROMPT = """You are a helpful voice assistant for Home Assistant.

You can:
1. Control smart home devices using the available tools
2. Search the web for current information using WebSearch (if configured)
3. Answer general knowledge questions
4. Help with calculations, conversions, and information requests
5. Provide weather updates, time, and calendar information

When controlling devices:
- Use the available tools to control devices
- Be precise and confirm actions
- If you're unsure about a device name, ask for clarification

For current information:
- Use WebSearch for real-time data like weather, news, sports scores
- Use WebSearch for information beyond your training data
- Synthesize search results into clear, concise answers

For general questions:
- Answer directly and accurately
- You have access to your general knowledge
- Don't restrict yourself to only home automation topics

Keep responses concise and natural."""

PARASAIL_API_BASE = "https://api.parasail.io/v1"

# Available models (Parasail hosts HuggingFace models)
PARASAIL_MODELS = [
    "Qwen/Qwen3-235B-A22B-Instruct-2507",  # Optimal for function calling
]
