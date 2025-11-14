"""Conversation support for Parasail."""
from __future__ import annotations

import logging
from typing import Literal

from openai import OpenAI

from homeassistant.components import conversation
from homeassistant.components.conversation import ConversationEntity, ConversationResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_API_KEY,
    CONF_MODEL,
    CONF_TEMPERATURE,
    CONF_MAX_TOKENS,
    CONF_TOP_P,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOP_P,
    DOMAIN,
    PARASAIL_API_BASE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Parasail conversation platform via config entry."""
    async_add_entities([ParasailConversationEntity(config_entry)])


class ParasailConversationEntity(ConversationEntity):
    """Parasail conversation agent."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self._attr_name = f"Parasail ({entry.data.get(CONF_MODEL, DEFAULT_MODEL)})"
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return "*"

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> ConversationResult:
        """Process a sentence."""
        _LOGGER.debug("Processing conversation input: %s", user_input.text)

        # Get configuration
        api_key = self.entry.data[CONF_API_KEY]
        model = self.entry.data.get(CONF_MODEL, DEFAULT_MODEL)
        temperature = self.entry.data.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)
        max_tokens = self.entry.data.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        top_p = self.entry.data.get(CONF_TOP_P, DEFAULT_TOP_P)

        # Create OpenAI client
        client = OpenAI(
            base_url=PARASAIL_API_BASE,
            api_key=api_key,
        )

        # Build messages - just use current user input
        # Note: Home Assistant's conversation API doesn't provide easy access to history
        messages = [{"role": "user", "content": user_input.text}]

        try:
            # Call Parasail API
            response = await self.hass.async_add_executor_job(
                lambda: client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                )
            )

            # Extract response text
            response_text = response.choices[0].message.content

            _LOGGER.debug("Parasail response: %s", response_text)

            # Create intent response
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(response_text)

            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id,
            )

        except Exception as err:
            _LOGGER.error("Error processing conversation: %s", err)

            # Create error response
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(
                f"Sorry, I encountered an error: {str(err)}"
            )

            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id,
            )
