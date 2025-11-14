# Testing the Parasail Conversation Integration

This directory contains tests for the Parasail Conversation Home Assistant custom component.

## Running Tests

### Setup

1. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install test dependencies:
```bash
pip install -r requirements_test.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Files

```bash
# Test helper functions only
pytest tests/test_helper_functions.py -v

# Test config flow only
pytest tests/test_config_flow.py -v
```

### Run Specific Tests

```bash
# Run a specific test class
pytest tests/test_helper_functions.py::TestFixLlmToolArgs -v

# Run a specific test method
pytest tests/test_helper_functions.py::TestFixLlmToolArgs::test_single_item_json_array_string -v
```

## Test Coverage

### Helper Functions (`test_helper_functions.py`)
- **`fix_llm_tool_args()`** - 16 test cases covering:
  - Single and multiple item JSON array strings
  - Whitespace handling
  - Different data types (strings, integers, floats, booleans, lists)
  - Invalid JSON handling
  - Mixed argument types
  - Edge cases (empty dict, nested structures)

### Config Flow (`test_config_flow.py`)
- **Input validation** - Tests `validate_input()`:
  - Success case with valid credentials
  - InvalidAuth exception on API errors

## What's Mocked

- **OpenAI Client** - All API calls to Parasail are mocked
  - No actual API requests are made during testing
  - Responses are predefined in test fixtures

## Adding New Tests

When adding new functionality, consider adding tests for:

1. **Helper functions** - Unit test any data transformation or utility functions
2. **Config/Options flow** - Test user input validation and error handling
3. **Conversation flow** - Mock LLM responses to test tool calling logic
4. **Error handling** - Test edge cases and error conditions

See existing test files for examples of mocking Home Assistant and external dependencies.
