# TODO - Parasail Conversation Integration

## Override Prompt Enhancements

### High Priority

- [ ] Add HassSetPosition tool to override_prompt for covers/blinds/garage doors
  - Example: "Open the blinds" → Call HassSetPosition with {"area": "...", "position": 100}
  - Example: "Close the garage door" → Call HassSetPosition with {"area": "garage", "domain": "cover", "position": 0}
  - Example: "Set blinds to 50%" → Call HassSetPosition with {"position": 50, "area": "..."}

- [ ] Add HassToggle tool to override_prompt for toggleable devices
  - Example: "Toggle the fan" → Call HassToggle with {"area": "...", "domain": "fan"}

- [ ] Expand Media Control section in override_prompt with specific examples
  - HassMediaPause: "Pause the music" → Call HassMediaPause with {"area": "..."}
  - HassMediaNext: "Next song" → Call HassMediaNext with {"area": "..."}
  - HassSetVolume: "Set volume to 50%" → Call HassSetVolume with {"volume_level": 50, "area": "..."}

### Optional/Lower Priority

- [ ] Consider adding HassFanSetSpeed tool to override_prompt for fan speed control
  - Example: "Set fan to medium" → Call HassFanSetSpeed

- [ ] Consider adding HassVacuumStart/HassVacuumReturnToBase tools to override_prompt for robot vacuums
  - Example: "Start the vacuum" → Call HassVacuumStart
  - Example: "Send the vacuum home" → Call HassVacuumReturnToBase

## Notes

- Location: `custom_components/parasail_conversation/conversation.py` around line 329
- Current tools already included: GetLiveContext, HassTurnOn, HassTurnOff, HassLightSet, HassClimateSetTemperature, HassMediaPause (basic mention)
