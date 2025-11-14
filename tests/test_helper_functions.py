"""Tests for helper functions in the Parasail Conversation integration."""
import pytest

from custom_components.parasail_conversation.utils import fix_llm_tool_args


class TestFixLlmToolArgs:
    """Test the fix_llm_tool_args helper function."""

    def test_single_item_json_array_string(self):
        """Test fixing single-item JSON array passed as string."""
        args = {"area_name": '["Family Room"]'}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"area_name": "Family Room"}

    def test_multiple_item_json_array_string(self):
        """Test fixing multi-item JSON array passed as string."""
        args = {"area_name": '["Family Room", "Kitchen"]'}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"area_name": ["Family Room", "Kitchen"]}

    def test_single_item_with_whitespace(self):
        """Test fixing single-item array with trailing/leading spaces."""
        args = {"area_name": '["  Family Room  "]'}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"area_name": "Family Room"}

    def test_multiple_items_with_whitespace(self):
        """Test fixing multi-item array with whitespace."""
        args = {"area_name": '["  Family Room  ", "  Kitchen  "]'}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"area_name": ["Family Room", "Kitchen"]}

    def test_normal_string_unchanged(self):
        """Test that normal strings are unchanged (except stripped)."""
        args = {"area_name": "Family Room"}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"area_name": "Family Room"}

    def test_normal_string_with_whitespace(self):
        """Test that normal strings get whitespace stripped."""
        args = {"area_name": "  Family Room  "}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"area_name": "Family Room"}

    def test_normal_list_unchanged(self):
        """Test that proper lists are unchanged."""
        args = {"area_name": ["Family Room", "Kitchen"]}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"area_name": ["Family Room", "Kitchen"]}

    def test_integer_unchanged(self):
        """Test that integers are unchanged."""
        args = {"brightness": 50}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"brightness": 50}

    def test_float_unchanged(self):
        """Test that floats are unchanged."""
        args = {"temperature": 72.5}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"temperature": 72.5}

    def test_boolean_unchanged(self):
        """Test that booleans are unchanged."""
        args = {"on_off": True}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"on_off": True}

    def test_invalid_json_array_string_unchanged(self):
        """Test that invalid JSON array strings are left as-is."""
        args = {"area_name": '["Incomplete'}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"area_name": '["Incomplete'}

    def test_multiple_args_mixed_types(self):
        """Test fixing multiple arguments with mixed types."""
        args = {
            "area_name": '["Family Room"]',
            "brightness": 50,
            "device_name": "  Kitchen Light  ",
            "on_off": True,
        }
        fixed = fix_llm_tool_args(args)
        assert fixed == {
            "area_name": "Family Room",
            "brightness": 50,
            "device_name": "Kitchen Light",
            "on_off": True,
        }

    def test_empty_dict(self):
        """Test that empty dict returns empty dict."""
        args = {}
        fixed = fix_llm_tool_args(args)
        assert fixed == {}

    def test_nested_structures_unchanged(self):
        """Test that nested structures (dicts/lists) are unchanged."""
        args = {"config": {"nested": "value"}}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"config": {"nested": "value"}}

    def test_json_array_with_numbers(self):
        """Test JSON array string with numbers."""
        args = {"values": "[1, 2, 3]"}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"values": [1, 2, 3]}

    def test_single_number_in_json_array(self):
        """Test single number in JSON array string gets unwrapped."""
        args = {"brightness": "[50]"}
        fixed = fix_llm_tool_args(args)
        assert fixed == {"brightness": 50}
