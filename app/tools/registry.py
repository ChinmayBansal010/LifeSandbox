from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    owner: str
    read_only: bool = True
    approval_required: bool = False
    timeout_seconds: float = 20.0
    retryable: bool = False
    risk: Literal["low", "medium", "high"] = "low"
    connection_requirement: str | None = None
    required_permissions: tuple[str, ...] = ()

    def model_description(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def validate(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("Tool arguments must be an object")
        props = self.parameters.get("properties", {})
        required = self.parameters.get("required", [])
        unknown = set(value) - set(props)
        if unknown:
            raise ValueError(f"Unknown argument: {sorted(unknown)[0]}")
        missing = set(required) - set(value)
        if missing:
            raise ValueError(f"Missing argument: {sorted(missing)[0]}")
        for key, item in value.items():
            spec = props[key]
            kind = spec.get("type")
            kinds = kind if isinstance(kind, list) else [kind]
            valid = (
                item is None
                and "null" in kinds
                or isinstance(item, str)
                and "string" in kinds
                or isinstance(item, bool)
                and "boolean" in kinds
                or isinstance(item, (int, float))
                and not isinstance(item, bool)
                and "number" in kinds
                or isinstance(item, int)
                and not isinstance(item, bool)
                and "integer" in kinds
                or isinstance(item, dict)
                and "object" in kinds
                or isinstance(item, list)
                and "array" in kinds
            )
            if kinds != [None] and not valid:
                raise ValueError(f"Argument '{key}' has an invalid type")
            if "enum" in spec and item not in spec["enum"]:
                raise ValueError(f"Argument '{key}' has an invalid value")
        return value


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool already registered: {definition.name}")
        self._tools[definition.name] = definition

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def discover(self, allowed: set[str] | None = None) -> list[dict[str, Any]]:
        return [
            item.model_description()
            for name, item in self._tools.items()
            if allowed is None or name in allowed
        ]


registry = ToolRegistry()


def register_tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
    owner: str,
    *,
    read_only: bool = True,
    approval_required: bool = False,
    timeout_seconds: float = 20.0,
    retryable: bool = False,
    risk: Literal["low", "medium", "high"] = "low",
    connection_requirement: str | None = None,
    required_permissions: tuple[str, ...] = (),
) -> None:
    registry.register(
        ToolDefinition(
            name,
            description,
            parameters,
            owner,
            read_only,
            approval_required,
            timeout_seconds,
            retryable,
            risk,
            connection_requirement,
            required_permissions,
        )
    )
