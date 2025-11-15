# Parasail Conversation for Home Assistant

A Home Assistant custom component that integrates [Parasail](https://www.parasail.io/) as a conversation agent. Use powerful AI models from Parasail to control your smart home and answer questions naturally.

## Features

- **Multiple Model Support**: Choose from various Parasail models including Llama, Qwen, Gemma, and Mistral
- **Configurable Parameters**: Adjust temperature, max tokens, and top_p for fine-tuned responses
- **Easy Setup**: Simple configuration through Home Assistant UI
- **HACS Compatible**: Install and update easily through HACS
- **Conversation History**: Maintains context across conversations

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS (category: Integration)
2. Search for "Parasail Conversation" and install
3. Restart Home Assistant

### Manual Installation

1. Download this repository
2. Copy the `custom_components/parasail_conversation` directory to your Home Assistant's `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "Parasail Conversation"
4. Enter your configuration:
   - **API Key**: Your Parasail API key (get one at [parasail.io](https://www.parasail.io/))
   - **Model**: Select your preferred model (default: parasail-qwen3-32b)
   - **Temperature**: Controls randomness (0.0-2.0, default: 0.7)
   - **Maximum Tokens**: Max response length (1-4096, default: 1000)
   - **Top P**: Nucleus sampling parameter (0.0-1.0, default: 1.0)

## Usage

### As a Conversation Agent

Once configured, you can use Parasail as your conversation agent:

1. Go to Settings → Voice Assistants
2. Select your assistant
3. Choose "Parasail" as the conversation agent

Now you can talk to your Home Assistant using Parasail's AI models!

## Configuration Options

You can update your configuration at any time:

1. Go to Settings → Devices & Services
2. Find "Parasail Conversation"
3. Click "Configure"
4. Update your settings

## Development

### Testing

This project includes a comprehensive test suite. To run the tests:

```bash
# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install test dependencies
pip install -r requirements_test.txt

# Run tests
pytest
```

See `tests/README.md` for more detailed testing documentation.

## License

This project is licensed under the MIT License.

## Credits

- Parasail API: [parasail.io](https://www.parasail.io/)
- Home Assistant: [home-assistant.io](https://www.home-assistant.io/)