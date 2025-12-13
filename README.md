# Parasail Conversation for Home Assistant

A Home Assistant custom component that integrates [Parasail](https://www.parasail.io/) as a conversation agent. Use powerful AI models from Parasail to control your smart home and answer questions naturally.

## Features

- **Powerful AI Model**: Uses Qwen/Qwen3-235B-A22B-Instruct-2507 for optimal function calling
- **Web Search Integration**: Search the web using Brave Search API for real-time information (optional)
- **Device Control**: Full smart home control through Home Assistant's LLM API
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
   - **Brave API Key** (Optional): Brave Search API key for web search (get from [brave.com/search/api](https://brave.com/search/api/))
   - **Model**: Select your preferred model (default: Qwen/Qwen3-235B-A22B-Instruct-2507)
   - **Temperature**: Controls randomness (0.0-2.0, default: 0.7)
   - **Maximum Tokens**: Max response length (1-100000, default: 4096)
   - **Top P**: Nucleus sampling parameter (0.0-1.0, default: 1.0)

## Usage

### As a Conversation Agent

Once configured, you can use Parasail as your conversation agent:

1. Go to Settings → Voice Assistants
2. Select your assistant
3. Choose "Parasail Conversation" as the conversation agent

Now you can talk to your Home Assistant using Parasail's AI models!

## Configuration Options

You can update your configuration at any time:

1. Go to Settings → Devices & Services
2. Find "Parasail Conversation"
3. Click "Configure"
4. Update your settings

### Web Search

To enable web search capabilities:

1. Get a Brave Search API key from [brave.com/search/api](https://brave.com/search/api/)
2. Add the API key in the integration configuration (either during initial setup or via Configure)
3. The assistant will automatically have access to the `WebSearch` tool
4. Ask questions like:
   - "What's the weather in San Francisco?"
   - "What's the latest news about SpaceX?"
   - "Search for the best Italian restaurants near me"

The LLM will automatically call the web search tool when needed and synthesize the results into a natural response.

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