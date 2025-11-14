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
    # Check what's currently registered
    current_handlers = intent.async_get(hass)
    climate_handlers = [h for h in current_handlers if "climate" in h.intent_type.lower() or "temperature" in h.intent_type.lower()]
    _LOGGER.info("Before registration - Climate-related intent handlers: %s",
                 [f"{h.intent_type} ({type(h).__module__}.{type(h).__name__})" for h in climate_handlers])

    # Register our custom intent handler, which will override the built-in one
    custom_handler = SetTemperatureIntent()
    intent.async_register(hass, custom_handler)

    # Check again after registration
    current_handlers = intent.async_get(hass)
    climate_handlers = [h for h in current_handlers if "climate" in h.intent_type.lower() or "temperature" in h.intent_type.lower()]
    _LOGGER.info("After registration - Climate-related intent handlers: %s",
                 [f"{h.intent_type} ({type(h).__module__}.{type(h).__name__})" for h in climate_handlers])
    _LOGGER.info("Custom climate intent handler registered with intent_type=%s", custom_handler.intent_type)


class SetTemperatureIntent(intent.IntentHandler):
    """Handle SetTemperature intents with auto mode support."""

    intent_type = INTENT_SET_TEMPERATURE
    description = (
        "Sets the target temperature of a climate device or entity. "
        "For auto mode thermostats, use target_temp_low for heating and target_temp_high for cooling. "
        "For single-mode thermostats, use temperature."
    )
    slot_schema = {
        vol.Optional("temperature"): vol.Coerce(float),
        vol.Optional("target_temp_low"): vol.Coerce(float),
        vol.Optional("target_temp_high"): vol.Coerce(float),
        vol.Optional("area"): intent.non_empty_string,
        vol.Optional("name"): intent.non_empty_string,
        vol.Optional("floor"): intent.non_empty_string,
        vol.Optional("preferred_area_id"): cv.string,
        vol.Optional("preferred_floor_id"): cv.string,
    }
    platforms = {CLIMATE_DOMAIN}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        _LOGGER.info("CUSTOM climate intent handler called with slots: %s", intent_obj.slots)
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        # Extract temperature parameters
        temperature: float | None = slots.get("temperature", {}).get("value")
        target_temp_low: float | None = slots.get("target_temp_low", {}).get("value")
        target_temp_high: float | None = slots.get("target_temp_high", {}).get("value")

        # Validate we have at least one temperature parameter
        if not any([temperature, target_temp_low, target_temp_high]):
            raise vol.error.MultipleInvalid("Must provide at least one temperature parameter")

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

        # Priority: explicit low/high temps, then single temp with auto-mode handling
        if target_temp_low is not None and target_temp_high is not None:
            # User explicitly provided both temps (for auto mode)
            service_data[ATTR_TARGET_TEMP_LOW] = target_temp_low
            service_data[ATTR_TARGET_TEMP_HIGH] = target_temp_high
            _LOGGER.info(
                "Setting explicit temp range for %s: low=%s, high=%s",
                climate_state.entity_id,
                target_temp_low,
                target_temp_high,
            )
        elif temperature is not None and current_hvac_mode == HVACMode.HEAT_COOL:
            # Single temp provided but thermostat is in auto mode
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
        elif temperature is not None:
            # Normal mode (heat, cool, etc.) - just set single temperature
            service_data[ATTR_TEMPERATURE] = temperature
            _LOGGER.info(
                "Thermostat %s is in %s mode, setting temperature to %s",
                climate_state.entity_id,
                current_hvac_mode,
                temperature,
            )
        else:
            raise vol.error.MultipleInvalid(
                "Must provide both target_temp_low and target_temp_high together, or provide temperature"
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
