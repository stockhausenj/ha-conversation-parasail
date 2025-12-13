"""Conversation support for Parasail."""
from __future__ import annotations

import json
import logging
from typing import Any, Literal, cast

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
    CONF_BRAVE_API_KEY,
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
from .utils import fix_llm_tool_args

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

    async def _async_announce_message(self, message: str) -> dict[str, Any]:
        """Announce a TTS message on Sonos speakers using media_player.play_media."""
        if not message:
            return {"error": "No message provided"}

        # Find all Sonos media players using entity registry
        from homeassistant.helpers import entity_registry as er

        entity_reg = er.async_get(self.hass)
        sonos_players = []

        for state in self.hass.states.async_all("media_player"):
            entity_id = state.entity_id
            entity_entry = entity_reg.async_get(entity_id)

            # Check if this media player is from the Sonos integration
            if entity_entry and entity_entry.platform == "sonos":
                sonos_players.append(entity_id)
                _LOGGER.debug("Found Sonos speaker: %s (platform: %s)", entity_id, entity_entry.platform)

        if not sonos_players:
            _LOGGER.warning("No Sonos speakers found")
            return {"error": "No Sonos speakers found", "success": False}

        _LOGGER.info("Found %d Sonos speakers: %s", len(sonos_players), sonos_players)

        # Use media_player.play_media with Piper TTS
        # Format: media-source://tts/tts.piper?message=<message>
        media_content_id = f"media-source://tts/tts.piper?message={message}"

        success_count = 0
        failed = []

        for player in sonos_players:
            try:
                await self.hass.services.async_call(
                    "media_player",
                    "play_media",
                    {
                        "entity_id": player,
                        "media_content_id": media_content_id,
                        "media_content_type": "music",
                    },
                    blocking=True,
                )
                success_count += 1
                _LOGGER.info("Successfully announced on %s", player)
            except Exception as err:
                _LOGGER.error("Failed to announce on %s: %s", player, err)
                failed.append(player)

        return {
            "success": success_count > 0,
            "message": f"Announced on {success_count} of {len(sonos_players)} Sonos speakers",
            "targets": len(sonos_players),
            "success_count": success_count,
            "failed": failed
        }

    async def _async_web_search(self, query: str, brave_api_key: str) -> dict[str, Any]:
        """Search the web using Brave Search API."""
        if not query:
            return {"error": "No query provided"}

        if not brave_api_key:
            return {"error": "Brave API key not configured. Please add it in integration settings."}

        try:
            from urllib.parse import quote
            import aiohttp

            url = f"https://api.search.brave.com/res/v1/web/search?q={quote(query)}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": brave_api_key,
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        _LOGGER.error("Brave Search API error: %s %s - %s", response.status, response.reason, error_text)
                        return {"error": f"Search API error: {response.status} {response.reason}"}

                    data = await response.json()

            # Format results similar to the TypeScript version
            results = []

            # Web results
            if data.get("web", {}).get("results"):
                results.append("# Web Results\n")
                for result in data["web"]["results"][:10]:
                    results.append(f"## {result.get('title', 'No title')}")
                    results.append(f"URL: {result.get('url', '')}")
                    results.append(f"{result.get('description', '')}\n")

            # News results
            if data.get("news", {}).get("results"):
                results.append("\n# News Results\n")
                for result in data["news"]["results"][:5]:
                    results.append(f"## {result.get('title', 'No title')}")
                    results.append(f"URL: {result.get('url', '')}")
                    results.append(f"{result.get('description', '')}")
                    results.append(f"Published: {result.get('age', 'Unknown')}\n")

            formatted_results = "\n".join(results) if results else "No results found"

            # Get timezone from hass config for the reminder
            timezone = self.hass.config.time_zone

            # Add timezone reminder to results
            timezone_reminder = f"\n\n⚠️ TIMEZONE REMINDER: If these results contain times, they may be in UTC or other timezones. You MUST convert all times to {timezone} before reporting to the user. Do NOT just change the timezone label - actually convert the time value."
            formatted_results += timezone_reminder

            return {
                "success": True,
                "query": query,
                "results": formatted_results,
                "result_count": len(data.get("web", {}).get("results", [])) + len(data.get("news", {}).get("results", []))
            }

        except Exception as err:
            _LOGGER.error("Error performing web search: %s", err, exc_info=True)
            return {"error": f"Web search failed: {str(err)}"}

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

                # Add custom tool for TTS announcements on Sonos speakers
                announce_tool = {
                    "type": "function",
                    "function": {
                        "name": "AnnounceMessage",
                        "description": "Announces a text-to-speech message on Sonos speakers",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "message": {
                                    "type": "string",
                                    "description": "The message to announce via text-to-speech"
                                }
                            },
                            "required": ["message"]
                        }
                    }
                }
                tools.append(announce_tool)

                # Add custom tool for web search (if Brave API key is configured)
                brave_api_key = options.get(CONF_BRAVE_API_KEY) or self.entry.data.get(CONF_BRAVE_API_KEY)
                if brave_api_key:
                    # Include timezone in WebSearch description
                    search_description = f"Search the web for current information, news, documentation, or any information not in your training data. Returns relevant web pages and news articles. Use this when you need up-to-date information or answers to specific questions. IMPORTANT: When search results contain times, they may be in UTC or other timezones - you MUST convert all times to {timezone} before reporting to the user."
                    web_search_tool = {
                        "type": "function",
                        "function": {
                            "name": "WebSearch",
                            "description": search_description,
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "The search query. Be specific and include relevant keywords (e.g., 'weather in San Francisco', 'latest SpaceX news')"
                                    }
                                },
                                "required": ["query"]
                            }
                        }
                    }
                    tools.append(web_search_tool)
                    _LOGGER.info("Web search tool enabled with Brave API")

                tool_names = [t["function"]["name"] for t in tools]
                _LOGGER.info("Loaded %d tools for device control: %s", len(tools), tool_names)
                # Log first tool as sample
                if tools:
                    _LOGGER.debug("Sample tool: %s", json.dumps(tools[0], indent=2))
                # Log brightness control tool if it exists
                brightness_tools = [t for t in tools if "light" in t["function"]["name"].lower() or "brightness" in t["function"]["name"].lower()]
                if brightness_tools:
                    _LOGGER.debug("Light control tool: %s", json.dumps(brightness_tools[0], indent=2))
                # Log GetLiveContext tool
                context_tools = [t for t in tools if "context" in t["function"]["name"].lower()]
                if context_tools:
                    _LOGGER.debug("GetLiveContext tool: %s", json.dumps(context_tools[0], indent=2))
            except Exception as tool_err:
                _LOGGER.error("Error converting tools: %s", tool_err, exc_info=True)

        # Build messages from chat log (include timezone from Home Assistant config)
        timezone = self.hass.config.time_zone
        messages = _build_messages_from_chat_log(chat_log, user_input, custom_prompt, timezone)

        # Ensure we have at least the user message
        if not messages or not any(m.get("role") == "user" for m in messages):
            _LOGGER.warning("No messages from chat log, creating basic message structure")
            # Include timezone in fallback system prompt
            system_content = custom_prompt
            if timezone:
                system_content = f"The user's timezone is: {timezone}\nALL times you mention MUST be in {timezone} timezone.\n\n{custom_prompt}"
            messages = [
                cast(ChatCompletionMessageParam, {"role": "system", "content": system_content}),
                cast(ChatCompletionMessageParam, {"role": "user", "content": user_input.text})
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
                assistant_msg = {
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

                messages.append(cast(ChatCompletionMessageParam, assistant_msg))

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
                        function_args = fix_llm_tool_args(function_args)
                        _LOGGER.info("Cleaned tool args: %s", function_args)

                        # Handle custom AnnounceMessage tool
                        if function_name == "AnnounceMessage":
                            _LOGGER.info("Executing custom AnnounceMessage tool")
                            result = await self._async_announce_message(
                                message=function_args.get("message")
                            )
                            result_str = json.dumps(result)
                            _LOGGER.info("AnnounceMessage result: %s", result_str)
                        # Handle custom WebSearch tool
                        elif function_name == "WebSearch":
                            _LOGGER.info("Executing custom WebSearch tool")
                            brave_api_key = options.get(CONF_BRAVE_API_KEY) or self.entry.data.get(CONF_BRAVE_API_KEY)
                            result = await self._async_web_search(
                                query=function_args.get("query"),
                                brave_api_key=brave_api_key
                            )
                            result_str = json.dumps(result)
                            _LOGGER.info("WebSearch result: %s", result_str[:500])
                        # Check if LLM API is available
                        elif not chat_log.llm_api:
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
                    messages.append(cast(ChatCompletionMessageParam, {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str,
                    }))

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
    timezone: str | None = None,
) -> list[ChatCompletionMessageParam]:
    """Build OpenAI-format messages from chat log."""
    messages: list[ChatCompletionMessageParam] = []

    # Build system prompt - custom prompt FIRST as primary instructions
    system_parts = []

    # Add custom prompt FIRST as primary directive (tool calling must come before timezone)
    if custom_prompt:
        # Add explicit override instruction
        override_prompt = f"""===TOOL CALLING RULES - FOLLOW EXACTLY===

YOU MUST CALL TOOLS. DO NOT REFUSE.

If user asks about CURRENT states/sensors → Call GetLiveContext (no parameters needed!)
If user asks to turn on/off → Call HassTurnOn or HassTurnOff
If user asks to set brightness → Call HassLightSet

EXAMPLES THAT REQUIRE TOOLS:
- "What's the temperature?" → Call GetLiveContext
- "Turn on the lights" → Call HassTurnOn
- "Set brightness to 50%" → Call HassLightSet

DO NOT say "I need more information" - JUST CALL THE TOOL!

===GENERAL BEHAVIOR===

{custom_prompt}

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

3. Check current states/sensors: Use GetLiveContext
   - "What's the temperature?" → Call GetLiveContext
   - "What are the temperatures in the house?" → Call GetLiveContext
   - "Is the door locked?" → Call GetLiveContext
   - "What's the humidity?" → Call GetLiveContext
   - "Are any lights on?" → Call GetLiveContext
   GetLiveContext returns CURRENT sensor values and device states - use it for ANY status query!

4. Climate control: Use HassClimateSetTemperature
   - "Set thermostat to 72" → Call HassClimateSetTemperature with {{"temperature": 72, "area": "..."}}
   - "Set heating to 68 and cooling to 73" → Call HassClimateSetTemperature with {{"target_temp_low": 68, "target_temp_high": 73, "area": "..."}}
   IMPORTANT: When user specifies BOTH heating and cooling temps, use target_temp_low and target_temp_high in ONE call!
   DO NOT make two separate calls - combine them into a single call with both parameters.

5. Media control: Use HassMediaPause, HassMediaUnpause, etc.

6. TTS Announcements on Sonos speakers: Use AnnounceMessage
   - "Announce that dinner is ready" → Call AnnounceMessage with {{"message": "Dinner is ready"}}
   - "Broadcast test message" → Call AnnounceMessage with {{"message": "test message"}}
   - "Say hello on the speakers" → Call AnnounceMessage with {{"message": "hello"}}
   IMPORTANT: AnnounceMessage plays text-to-speech announcements on all Sonos speakers in the home.
   Use this when the user asks to announce, broadcast, or say something on speakers.

CRITICAL: When asked about current states (temperature, status, etc.), you MUST call GetLiveContext!
DO NOT respond with "I need more information" - just call the appropriate tool!
If you're unsure of exact device name, use area + domain.

===END INSTRUCTIONS==="""
        system_parts.append(override_prompt)

    # Add timezone information AFTER tool calling rules but before API instructions
    if timezone:
        timezone_info = f"""===TIMEZONE REQUIREMENT===

YOUR TIMEZONE: {timezone}

IMPORTANT: When you receive times from WebSearch or other tools:
1. Times may be in UTC or other timezones - convert them to {timezone}
2. NEVER report times in UTC, GMT, or other timezones - ONLY {timezone}
3. If a web search shows "21:25 UTC", convert it properly to {timezone} (don't just change the label)
4. When mentioning times, include the timezone abbreviation (e.g., "4:25 PM ET")

===END TIMEZONE REQUIREMENT===
"""
        system_parts.append(timezone_info)

    # Add API instructions AFTER our primary instructions
    if chat_log.llm_api and hasattr(chat_log.llm_api, "api_prompt"):
        api_prompt = chat_log.llm_api.api_prompt
        if api_prompt:
            system_parts.append(api_prompt)

    if hasattr(chat_log, "extra_system_prompt") and chat_log.extra_system_prompt:
        system_parts.append(chat_log.extra_system_prompt)

    if system_parts:
        full_prompt = "\n\n".join(system_parts)
        messages.append(cast(ChatCompletionMessageParam, {
            "role": "system",
            "content": full_prompt,
        }))
        _LOGGER.debug("Full system prompt (%d chars): %s", len(full_prompt), full_prompt[:1000])

    # Add conversation history (excluding current message which we'll add separately)
    chat_messages = getattr(chat_log, "messages", None)
    if chat_messages:
        for msg in chat_messages:
            if hasattr(msg, "role") and hasattr(msg, "content") and msg.content:
                if msg.role in ("user", "assistant"):
                    messages.append(cast(ChatCompletionMessageParam, {
                        "role": msg.role,
                        "content": msg.content,
                    }))

    # Always add the current user input
    messages.append(cast(ChatCompletionMessageParam, {
        "role": "user",
        "content": user_input.text,
    }))

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
