import pytest
from app.tools.registry import ToolDefinition

@pytest.fixture
def definition():
    return ToolDefinition("sample.tool","Sample",{"type":"object","properties":{"count":{"type":"integer"},"enabled":{"type":"boolean"},"name":{"type":"string"}},"required":["count"]},"tests")

@pytest.mark.parametrize("value", [True, 1.5, "1", None])
def test_integer_argument_rejects_non_integer_values(definition, value):
    with pytest.raises(ValueError):
        definition.validate({"count":value})

def test_boolean_is_not_accepted_as_integer(definition):
    with pytest.raises(ValueError):
        definition.validate({"count":True})

def test_optional_fields_can_be_omitted(definition):
    assert definition.validate({"count":3}) == {"count":3}

def test_unknown_fields_are_rejected(definition):
    with pytest.raises(ValueError, match="Unknown argument"):
        definition.validate({"count":3,"surprise":True})
