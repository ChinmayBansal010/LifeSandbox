import pytest

from app.tools.registry import ToolDefinition


@pytest.fixture
def definition():
    return ToolDefinition(
        "sample.tool",
        "Sample",
        {
            "type": "object",
            "properties": {"count": {"type": "integer"}, "enabled": {"type": "boolean"}, "name": {"type": "string"}},
            "required": ["count"],
        },
        "tests",
    )


@pytest.mark.parametrize("value", [True, 1.5, "1", None])
def test_integer_argument_rejects_non_integer_values(definition, value):
    with pytest.raises(ValueError):
        definition.validate({"count": value})


def test_boolean_is_not_accepted_as_integer(definition):
    with pytest.raises(ValueError):
        definition.validate({"count": True})


def test_optional_fields_can_be_omitted(definition):
    assert definition.validate({"count": 3}) == {"count": 3}


def test_unknown_fields_are_rejected(definition):
    with pytest.raises(ValueError, match="Unknown argument"):
        definition.validate({"count": 3, "surprise": True})


def test_string_length_constraints_are_enforced():
    definition = ToolDefinition(
        "sample.text",
        "Sample",
        {
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 2, "maxLength": 5}},
            "required": ["query"],
        },
        "tests",
    )
    assert definition.validate({"query": "okay"})["query"] == "okay"
    for query in ("x", "toolong"):
        with pytest.raises(ValueError):
            definition.validate({"query": query})


def test_numeric_bounds_are_enforced():
    definition = ToolDefinition(
        "sample.limit",
        "Sample",
        {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 10}},
            "required": ["limit"],
        },
        "tests",
    )
    assert definition.validate({"limit": 5})["limit"] == 5
    for limit in (0, 11):
        with pytest.raises(ValueError):
            definition.validate({"limit": limit})


def test_array_item_count_constraints_are_enforced():
    definition = ToolDefinition(
        "sample.list",
        "Sample",
        {
            "type": "object",
            "properties": {"items": {"type": "array", "minItems": 1, "maxItems": 2}},
            "required": ["items"],
        },
        "tests",
    )
    assert definition.validate({"items": ["a"]})["items"] == ["a"]
    for items in ([], ["a", "b", "c"]):
        with pytest.raises(ValueError):
            definition.validate({"items": items})
