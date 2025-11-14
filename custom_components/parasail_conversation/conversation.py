"""Conversation support for Parasail."""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from voluptuous_openapi import convert

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

        # Log the request for debugging
        _LOGGER.debug("Sending %d messages to Parasail", len(messages))
        _LOGGER.debug("Messages: %s", messages)

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

    # Build system prompt from LLM API prompt and extra system prompt
    system_parts = []

    if chat_log.llm_api and hasattr(chat_log.llm_api, "api_prompt"):
        system_parts.append(chat_log.llm_api.api_prompt)

    if chat_log.extra_system_prompt:
        system_parts.append(chat_log.extra_system_prompt)

    if system_parts:
        messages.append({
            "role": "system",
            "content": "\n\n".join(system_parts),
        })

    # Add conversation messages
    if hasattr(chat_log, "messages"):
        for msg in chat_log.messages:
            if hasattr(msg, "role") and hasattr(msg, "content"):
                if msg.role in ("user", "assistant"):
                    messages.append({
                        "role": msg.role,
                        "content": msg.content,
                    })

    return messages


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
