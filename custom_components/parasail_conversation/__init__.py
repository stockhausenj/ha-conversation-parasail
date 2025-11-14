"""The Parasail Conversation integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from . import climate_intent

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CONVERSATION]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Parasail Conversation from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Register custom climate intent handler AFTER all components have started
    # This ensures it's the final handler and won't be overwritten
    from homeassistant.core import callback
    from homeassistant.const import EVENT_HOMEASSISTANT_STARTED

    @callback
    def register_climate_intent(_):
        """Register our custom climate intent handler."""
        # Schedule this as a task to ensure it runs after event handlers
        async def _register():
            await climate_intent.async_setup_intents(hass)
            _LOGGER.info("Registered custom climate intent handler after HA startup")

        hass.async_create_task(_register())

    # If HA is already started, register immediately
    if hass.is_running:
        register_climate_intent(None)
    else:
        # Otherwise, wait for startup event
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, register_climate_intent)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
