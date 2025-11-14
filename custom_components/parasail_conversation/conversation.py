"""Conversation support for Parasail."""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from homeassistant.components import conversation
from homeassistant.components.conversation import ConversationEntity, ConversationResult
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
        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                llm_api_id if llm_api_id else None,
                custom_prompt,
                user_input.extra_system_prompt,
            )
        except Exception as err:
            _LOGGER.error("Error providing LLM data: %s", err)
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(
                f"Sorry, I couldn't initialize device control: {str(err)}"
            )
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id,
            )

        # Create OpenAI client
        client = OpenAI(
            base_url=PARASAIL_API_BASE,
            api_key=api_key,
        )

        # Convert tools to OpenAI format
        tools = None
        if chat_log.llm_api and chat_log.llm_api.tools:
            tools = _convert_tools_to_openai_format(chat_log.llm_api.tools)
            _LOGGER.debug("Loaded %d tools for device control", len(tools))

        # Build messages from chat log
        messages = _build_messages_from_chat_log(chat_log)

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

                response = await self.hass.async_add_executor_job(
                    lambda: client.chat.completions.create(**completion_args)
                )

                assistant_message = response.choices[0].message

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
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
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
                })

                # Execute each tool call
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args_str = tool_call.function.arguments

                    _LOGGER.debug(
                        "Executing tool: %s with args: %s",
                        function_name,
                        function_args_str,
                    )

                    try:
                        # Parse arguments
                        function_args = json.loads(function_args_str)

                        # Execute the tool via LLM API
                        tool_input = llm.ToolInput(
                            tool_name=function_name,
                            tool_args=function_args,
                        )

                        tool_result = await chat_log.llm_api.async_call_tool(tool_input)
                        result_str = json.dumps(tool_result)

                        _LOGGER.debug("Tool result: %s", result_str)

                    except Exception as tool_err:
                        _LOGGER.error("Error executing tool %s: %s", function_name, tool_err)
                        result_str = json.dumps({"error": str(tool_err)})

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str,
                    })

                # Continue loop to get next response from LLM

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


def _build_messages_from_chat_log(chat_log: ChatLog) -> list[ChatCompletionMessageParam]:
    """Build OpenAI-format messages from chat log."""
    messages: list[ChatCompletionMessageParam] = []

    # Add system prompt
    system_prompt = chat_log.get_system_prompt()
    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt,
        })

    # Add conversation messages
    for msg in chat_log.messages:
        if msg.role == "user":
            messages.append({
                "role": "user",
                "content": msg.content,
            })
        elif msg.role == "assistant":
            messages.append({
                "role": "assistant",
                "content": msg.content,
            })

    return messages


def _convert_tools_to_openai_format(tools: list[llm.Tool]) -> list[dict[str, Any]]:
    """Convert Home Assistant LLM tools to OpenAI function calling format."""
    openai_tools = []

    for tool in tools:
        # Convert voluptuous schema to JSON schema
        parameters = _voluptuous_to_json_schema(tool.parameters)

        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or tool.name,
                "parameters": parameters,
            },
        })

    return openai_tools


def _voluptuous_to_json_schema(schema: Any) -> dict[str, Any]:
    """Convert voluptuous schema to JSON schema format."""
    # Basic conversion - this handles simple schemas
    # For more complex schemas, Home Assistant has serialization helpers

    if not hasattr(schema, "schema"):
        return {"type": "object", "properties": {}, "required": []}

    properties = {}
    required = []

    schema_dict = schema.schema if hasattr(schema, "schema") else {}

    for key, value in schema_dict.items():
        # Extract the actual key name
        if hasattr(key, "schema"):
            key_name = key.schema
            is_required = hasattr(key, "marker") and key.marker is not None
        else:
            key_name = str(key)
            is_required = False

        # Basic type mapping
        properties[key_name] = {"type": "string"}  # Default to string

        if is_required:
            required.append(key_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }
