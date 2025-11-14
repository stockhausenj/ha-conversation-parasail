"""Tests for the Parasail Conversation config flow."""
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.parasail_conversation.config_flow import (
    InvalidAuth,
)
from custom_components.parasail_conversation.const import (
    CONF_API_KEY,
    CONF_MODEL,
    DEFAULT_MODEL,
)


class TestValidateInput:
    """Test the validate_input function."""

    @pytest.mark.asyncio
    async def test_validate_input_success(self, hass: HomeAssistant, mock_openai_client):
        """Test that validate_input succeeds with valid API key."""
        from custom_components.parasail_conversation.config_flow import validate_input

        data = {
            CONF_API_KEY: "test_api_key",
            CONF_MODEL: DEFAULT_MODEL,
        }

        with patch(
            "custom_components.parasail_conversation.config_flow.OpenAI",
            mock_openai_client,
        ):
            result = await validate_input(hass, data)

        assert result == {"title": f"Parasail ({DEFAULT_MODEL})"}

    @pytest.mark.asyncio
    async def test_validate_input_invalid_auth(self, hass: HomeAssistant):
        """Test that validate_input raises InvalidAuth on API error."""
        from custom_components.parasail_conversation.config_flow import validate_input

        data = {
            CONF_API_KEY: "invalid_key",
            CONF_MODEL: DEFAULT_MODEL,
        }

        with patch(
            "custom_components.parasail_conversation.config_flow.OpenAI"
        ) as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = Exception(
                "API Error"
            )

            with pytest.raises(InvalidAuth):
                await validate_input(hass, data)
