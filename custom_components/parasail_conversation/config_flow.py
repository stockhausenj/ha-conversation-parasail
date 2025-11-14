"""Config flow for Parasail Conversation integration."""
from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

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
    PARASAIL_MODELS,
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    def _test_connection():
        """Test connection to Parasail API."""
        client = OpenAI(
            base_url=PARASAIL_API_BASE,
            api_key=data[CONF_API_KEY],
        )
        return client.chat.completions.create(
            model=data.get(CONF_MODEL, DEFAULT_MODEL),
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10,
        )

    try:
        # Test the API key with a simple completion
        await hass.async_add_executor_job(_test_connection)
    except Exception as err:
        _LOGGER.error("Failed to connect to Parasail API: %s", err)
        raise InvalidAuth from err

    return {"title": f"Parasail ({data.get(CONF_MODEL, DEFAULT_MODEL)})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Parasail Conversation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_MODEL, default=DEFAULT_MODEL): vol.In(
                        PARASAIL_MODELS
                    ),
                    vol.Optional(CONF_TEMPERATURE, default=DEFAULT_TEMPERATURE): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0, max=2.0)
                    ),
                    vol.Optional(CONF_MAX_TOKENS, default=DEFAULT_MAX_TOKENS): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=4096)
                    ),
                    vol.Optional(CONF_TOP_P, default=DEFAULT_TOP_P): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0, max=1.0)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Parasail Conversation."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get available LLM APIs
        apis = await llm.async_get_apis(self.hass)
        api_choices = {api.id: api.name for api in apis}

        # Get current options, fallback to data if options not set
        config_entry = self.config_entry
        options = config_entry.options or config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL,
                        default=options.get(CONF_MODEL, DEFAULT_MODEL),
                    ): vol.In(PARASAIL_MODELS),
                    vol.Optional(
                        CONF_LLM_HASS_API,
                        description={"suggested_value": options.get(CONF_LLM_HASS_API, "assist")},
                    ): vol.In(api_choices),
                    vol.Optional(
                        CONF_PROMPT,
                        description={"suggested_value": options.get(CONF_PROMPT, DEFAULT_PROMPT)},
                    ): str,
                    vol.Optional(
                        CONF_TEMPERATURE,
                        default=options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
                    ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
                    vol.Optional(
                        CONF_MAX_TOKENS,
                        default=options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=4096)),
                    vol.Optional(
                        CONF_TOP_P,
                        default=options.get(CONF_TOP_P, DEFAULT_TOP_P),
                    ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
                }
            ),
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
