"""Common test fixtures for Parasail Conversation tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.parasail_conversation.const import (
    CONF_API_KEY,
    CONF_MODEL,
    DEFAULT_MODEL,
)


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    with patch("custom_components.parasail_conversation.config_flow.OpenAI") as mock:
        client = MagicMock()
        mock.return_value = client

        # Mock successful completion
        completion = MagicMock()
        completion.choices = [MagicMock()]
        completion.choices[0].message.content = "Test response"

        client.chat.completions.create.return_value = completion

        yield mock


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        CONF_API_KEY: "test_api_key",
        CONF_MODEL: DEFAULT_MODEL,
    }
    entry.options = {}
    return entry
