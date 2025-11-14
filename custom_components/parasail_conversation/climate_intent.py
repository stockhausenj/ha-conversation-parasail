"""Custom climate intent handler that supports auto mode."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent

_LOGGER = logging.getLogger(__name__)

# Intent type must match what Home Assistant expects
INTENT_SET_TEMPERATURE = "HassClimateSetTemperature"

# Default temperature spread for auto mode (degrees)
AUTO_MODE_TEMP_SPREAD = 2.0


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the custom climate intents."""
    # Register our custom intent handler, which will override the built-in one
    intent.async_register(hass, SetTemperatureIntent())
    _LOGGER.info("Registered custom climate intent handler with auto mode support")


class SetTemperatureIntent(intent.IntentHandler):
    """Handle SetTemperature intents with auto mode support."""

    intent_type = INTENT_SET_TEMPERATURE
    description = "Sets the target temperature of a climate device or entity"
    slot_schema = {
        vol.Required("temperature"): vol.Coerce(float),
        vol.Optional("area"): intent.non_empty_string,
        vol.Optional("name"): intent.non_empty_string,
        vol.Optional("floor"): intent.non_empty_string,
        vol.Optional("preferred_area_id"): cv.string,
        vol.Optional("preferred_floor_id"): cv.string,
    }
    platforms = {CLIMATE_DOMAIN}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        temperature: float = slots["temperature"]["value"]

        name: str | None = None
        if "name" in slots:
            name = slots["name"]["value"]

        area_name: str | None = None
        if "area" in slots:
            area_name = slots["area"]["value"]

        floor_name: str | None = None
        if "floor" in slots:
            floor_name = slots["floor"]["value"]

        match_constraints = intent.MatchTargetsConstraints(
            name=name,
            area_name=area_name,
            floor_name=floor_name,
            domains=[CLIMATE_DOMAIN],
            assistant=intent_obj.assistant,
            features=ClimateEntityFeature.TARGET_TEMPERATURE,
            single_target=True,
        )
        match_preferences = intent.MatchTargetsPreferences(
            area_id=slots.get("preferred_area_id", {}).get("value"),
            floor_id=slots.get("preferred_floor_id", {}).get("value"),
        )
        match_result = intent.async_match_targets(
            hass, match_constraints, match_preferences
        )
        if not match_result.is_match:
            raise intent.MatchFailedError(
                result=match_result, constraints=match_constraints
            )

        assert match_result.states
        climate_state = match_result.states[0]

        # Check if thermostat is in auto mode (heat_cool)
        current_hvac_mode = climate_state.state
        service_data = {}

        if current_hvac_mode == HVACMode.HEAT_COOL:
            # In auto mode, we need to set both low and high temps
            # Set them with a reasonable spread around the target
            service_data[ATTR_TARGET_TEMP_LOW] = temperature - (AUTO_MODE_TEMP_SPREAD / 2)
            service_data[ATTR_TARGET_TEMP_HIGH] = temperature + (AUTO_MODE_TEMP_SPREAD / 2)
            _LOGGER.info(
                "Thermostat %s is in auto mode, setting temp range: low=%s, high=%s (target was %s)",
                climate_state.entity_id,
                service_data[ATTR_TARGET_TEMP_LOW],
                service_data[ATTR_TARGET_TEMP_HIGH],
                temperature,
            )
        else:
            # Normal mode (heat, cool, etc.) - just set single temperature
            service_data[ATTR_TEMPERATURE] = temperature
            _LOGGER.info(
                "Thermostat %s is in %s mode, setting temperature to %s",
                climate_state.entity_id,
                current_hvac_mode,
                temperature,
            )

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            service_data=service_data,
            target={ATTR_ENTITY_ID: climate_state.entity_id},
            blocking=True,
        )

        response = intent_obj.create_response()
        response.async_set_results(
            success_results=[
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    name=climate_state.name,
                    id=climate_state.entity_id,
                )
            ]
        )
        response.async_set_states(matched_states=[climate_state])
        return response
