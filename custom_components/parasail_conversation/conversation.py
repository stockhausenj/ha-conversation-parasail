"""Conversation support for Parasail."""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    ConversationEntity,
    ConversationEntityFeature,
    ConversationResult,
)
from homeassistant.components.conversation.chat_log import ChatLog
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent, llm
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_API_KEY,
    CONF_MODEL,
    CONF_TEMPERATURE,
    CONF_MAX_TOKENS,
    CONF_TOP_P,
    CONF_LLM_HASS_API,
    CONF_PROMPT,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOP_P,
    DEFAULT_PROMPT,
    DOMAIN,
    PARASAIL_API_BASE,
)

_LOGGER = logging.getLogger(__name__)

# Maximum number of tool calling iterations
MAX_TOOL_ITERATIONS = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Parasail conversation platform via config entry."""
    async_add_entities([ParasailConversationEntity(config_entry)])


class ParasailConversationEntity(ConversationEntity):
    """Parasail conversation agent with device control support."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self._attr_name = f"Parasail ({entry.data.get(CONF_MODEL, DEFAULT_MODEL)})"
        self._attr_unique_id = entry.entry_id
        self._attr_supported_features = ConversationEntityFeature.CONTROL

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return "*"

    async def _async_handle_message(
        self, user_input: conversation.ConversationInput, chat_log: ChatLog
    ) -> ConversationResult:
        """Process a message with device control support."""
        _LOGGER.debug("Processing conversation input: %s", user_input.text)

        # Get configuration - options override data
        options = self.entry.options or self.entry.data
        api_key = self.entry.data[CONF_API_KEY]
        model = options.get(CONF_MODEL, DEFAULT_MODEL)
        temperature = options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)
        max_tokens = options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        top_p = options.get(CONF_TOP_P, DEFAULT_TOP_P)

        # Get LLM API and prompt configuration
        llm_api_id = options.get(CONF_LLM_HASS_API)
        custom_prompt = options.get(CONF_PROMPT, DEFAULT_PROMPT)

        # Provide LLM data to chat log (this loads tools and context)
        # Only if LLM API is configured
        if llm_api_id:
            try:
                await chat_log.async_provide_llm_data(
                    user_input.as_llm_context(DOMAIN),
                    llm_api_id,
                    custom_prompt,
                    user_input.extra_system_prompt,
                )
                _LOGGER.info("LLM data provided with API: %s", llm_api_id)
            except Exception as err:
                _LOGGER.error("Error providing LLM data: %s", err, exc_info=True)
                # Continue without tools rather than failing
        else:
            _LOGGER.info("No LLM API configured, running without device control tools")

        # Create OpenAI client (in executor to avoid blocking SSL operations)
        client = await self.hass.async_add_executor_job(
            lambda: OpenAI(
                base_url=PARASAIL_API_BASE,
                api_key=api_key,
            )
        )

        # Convert tools to OpenAI format
        tools = None
        if chat_log.llm_api and chat_log.llm_api.tools:
            try:
                tools = _convert_tools_to_openai_format(chat_log.llm_api.tools)
                tool_names = [t["function"]["name"] for t in tools]
                _LOGGER.info("Loaded %d tools for device control: %s", len(tools), tool_names)
                # Log first tool as sample
                if tools:
                    _LOGGER.debug("Sample tool: %s", json.dumps(tools[0], indent=2))
                # Log brightness control tool if it exists
                brightness_tools = [t for t in tools if "light" in t["function"]["name"].lower() or "brightness" in t["function"]["name"].lower()]
                if brightness_tools:
                    _LOGGER.debug("Light control tool: %s", json.dumps(brightness_tools[0], indent=2))
            except Exception as tool_err:
                _LOGGER.error("Error converting tools: %s", tool_err, exc_info=True)

        # Build messages from chat log
        messages = _build_messages_from_chat_log(chat_log, user_input, custom_prompt)

        # Ensure we have at least the user message
        if not messages or not any(m.get("role") == "user" for m in messages):
            _LOGGER.warning("No messages from chat log, creating basic message structure")
            messages = [
                {"role": "system", "content": custom_prompt},
                {"role": "user", "content": user_input.text}
            ]

        # Log the request for debugging
        _LOGGER.info("Sending %d messages to Parasail", len(messages))
        for idx, msg in enumerate(messages):
            _LOGGER.debug("Message %d: %s", idx, json.dumps(msg, indent=2)[:500])

        # Tool calling loop
        iteration = 0
        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            try:
                # Call Parasail API
                completion_args: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                }

                if tools:
                    completion_args["tools"] = tools
                    completion_args["tool_choice"] = "auto"

                _LOGGER.debug("Calling Parasail API with args: model=%s, num_messages=%d, num_tools=%s",
                             model, len(messages), len(tools) if tools else 0)

                try:
                    response = await self.hass.async_add_executor_job(
                        lambda: client.chat.completions.create(**completion_args)
                    )
                except Exception as api_err:
                    _LOGGER.error("Parasail API error: %s", api_err, exc_info=True)
                    _LOGGER.error("Request had %d messages, %d tools",
                                 len(messages), len(tools) if tools else 0)
                    raise

                assistant_message = response.choices[0].message

                _LOGGER.info(
                    "Parasail response: content='%s', has_tool_calls=%s",
                    assistant_message.content,
                    bool(assistant_message.tool_calls),
                )

                # Check if we're done (no tool calls)
                if not assistant_message.tool_calls:
                    # Extract final response text
                    response_text = assistant_message.content or "I'm not sure how to respond to that."

                    intent_response = intent.IntentResponse(language=user_input.language)
                    intent_response.async_set_speech(response_text)

                    return conversation.ConversationResult(
                        response=intent_response,
                        conversation_id=user_input.conversation_id,
                    )

                # Process tool calls
                # Note: content can be None when there are tool calls
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                        for tool_call in assistant_message.tool_calls
                    ],
                }

                # Only add content if it's not None/empty
                if assistant_message.content:
                    assistant_msg["content"] = assistant_message.content

                messages.append(assistant_msg)

                # Execute each tool call
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args_str = tool_call.function.arguments

                    _LOGGER.info(
                        "LLM requested tool: %s with args: %s",
                        function_name,
                        function_args_str,
                    )

                    try:
                        # Parse arguments
                        function_args = json.loads(function_args_str)
                        _LOGGER.debug("Raw parsed tool args: %s", function_args)

                        # Fix LLM sending JSON arrays as strings (e.g., '["item"]' instead of "item" or ["item"])
                        function_args = _fix_llm_tool_args(function_args)
                        _LOGGER.info("Cleaned tool args: %s", function_args)

                        # Check if LLM API is available
                        if not chat_log.llm_api:
                            _LOGGER.error("LLM API not available! Cannot execute tool %s", function_name)
                            result_str = json.dumps({"error": "LLM API not configured"})
                        else:
                            # Execute the tool via LLM API
                            tool_input = llm.ToolInput(
                                tool_name=function_name,
                                tool_args=function_args,
                            )

                            _LOGGER.debug("Calling LLM API tool with input: %s", tool_input)
                            tool_result = await chat_log.llm_api.async_call_tool(tool_input)
                            result_str = json.dumps(tool_result)

                            _LOGGER.info("Tool %s executed successfully. Result: %s", function_name, result_str)

                    except Exception as tool_err:
                        _LOGGER.error("Error executing tool %s: %s", function_name, tool_err, exc_info=True)
                        # Provide helpful error message back to the LLM
                        error_msg = str(tool_err)
                        if "MatchFailedError" in error_msg:
                            result_str = json.dumps({
                                "error": "Could not find matching devices. Try being more specific with device names or call the tool separately for each area/device.",
                                "details": error_msg
                            })
                        else:
                            result_str = json.dumps({"error": error_msg})

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str,
                    })

                # Continue loop to get next response from LLM
                _LOGGER.info(
                    "Completed %d tool calls, continuing conversation (iteration %d/%d)",
                    len(assistant_message.tool_calls),
                    iteration,
                    MAX_TOOL_ITERATIONS,
                )

            except Exception as err:
                _LOGGER.error("Error during conversation processing: %s", err)
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_speech(
                    f"Sorry, I encountered an error: {str(err)}"
                )
                return conversation.ConversationResult(
                    response=intent_response,
                    conversation_id=user_input.conversation_id,
                )

        # Max iterations reached
        _LOGGER.warning("Max tool calling iterations reached")
        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(
            "I tried to complete your request but it required too many steps. Please try breaking it into smaller requests."
        )
        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=user_input.conversation_id,
        )


def _build_messages_from_chat_log(
    chat_log: ChatLog,
    user_input: conversation.ConversationInput,
    custom_prompt: str,
) -> list[ChatCompletionMessageParam]:
    """Build OpenAI-format messages from chat log."""
    messages: list[ChatCompletionMessageParam] = []

    # Build system prompt - custom prompt LAST to override API restrictions
    system_parts = []

    if chat_log.llm_api and hasattr(chat_log.llm_api, "api_prompt"):
        api_prompt = chat_log.llm_api.api_prompt
        if api_prompt:
            system_parts.append(api_prompt)

    if hasattr(chat_log, "extra_system_prompt") and chat_log.extra_system_prompt:
        system_parts.append(chat_log.extra_system_prompt)

    # Add custom prompt LAST so it takes priority over API restrictions
    if custom_prompt:
        # Add explicit override instruction
        override_prompt = f"""{custom_prompt}

===CRITICAL INSTRUCTIONS===

GENERAL QUESTIONS:
- Answer general knowledge questions (capitals, math, facts) directly
- Do NOT say you need more information for general topics
- You have full access to your training knowledge

DEVICE CONTROL - YOU MUST USE TOOLS:
When users request device control, YOU MUST call the appropriate tool:

1. Turn on/off: Use HassTurnOn or HassTurnOff
   - "Turn on living room light" → Call HassTurnOn with {{"area": "living room", "domain": "light"}}

2. Set brightness/color: Use HassLightSet
   - "Set living room light to 50%" → Call HassLightSet with {{"area": "living room", "brightness": 50}}
   - "Make bedroom light blue" → Call HassLightSet with {{"area": "bedroom", "color": "blue"}}

3. Check current states: Use GetLiveContext
   - "What's the temperature?" → Call GetLiveContext

4. Climate control: Use HassClimateSetTemperature
5. Media control: Use HassMediaPause, HassMediaUnpause, etc.

DO NOT respond with "I need more information" for device control - just call the tool with available info!
If you're unsure of exact device name, use area + domain.

===END INSTRUCTIONS==="""
        system_parts.append(override_prompt)

    if system_parts:
        full_prompt = "\n\n".join(system_parts)
        messages.append({
            "role": "system",
            "content": full_prompt,
        })
        _LOGGER.debug("Full system prompt (%d chars): %s", len(full_prompt), full_prompt[:1000])

    # Add conversation history (excluding current message which we'll add separately)
    if hasattr(chat_log, "messages") and chat_log.messages:
        for msg in chat_log.messages:
            if hasattr(msg, "role") and hasattr(msg, "content") and msg.content:
                if msg.role in ("user", "assistant"):
                    messages.append({
                        "role": msg.role,
                        "content": msg.content,
                    })

    # Always add the current user input
    messages.append({
        "role": "user",
        "content": user_input.text,
    })

    return messages


def _fix_llm_tool_args(args: dict[str, Any]) -> dict[str, Any]:
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


def _convert_tools_to_openai_format(tools: list[llm.Tool]) -> list[dict[str, Any]]:
    """Convert Home Assistant LLM tools to OpenAI function calling format."""
    openai_tools = []

    for tool in tools:
        try:
            # Use voluptuous_openapi to convert schema
            parameters = convert(tool.parameters, custom_serializer=llm.selector_serializer)
        except Exception as err:
            _LOGGER.warning("Error converting schema for tool %s: %s, using basic schema", tool.name, err)
            parameters = {"type": "object", "properties": {}}

        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or tool.name,
                "parameters": parameters,
            },
        })

    return openai_tools
