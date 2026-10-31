import re
from dataclasses import dataclass, field
from typing import Any, Literal

CapabilityStatus = Literal[
    "available",
    "connected",
    "requires_setup",
    "requires_connection",
    "permission_required",
    "disabled",
    "unavailable",
    "degraded",
]


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
    provider_id: str = "local"
    category: str = "productivity"
    version: str = "1"
    output_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object"})
    input_sensitivity: Literal["public", "personal", "sensitive"] = "personal"
    output_sensitivity: Literal["public", "personal", "sensitive"] = "personal"
    returns_external_urls: bool = False
    enabled: bool = True

    @property
    def display_name(self) -> str:
        return self.name.replace(".", " · ").replace("_", " ").title()

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
        _validate_schema(self.parameters, value, "arguments")
        if not isinstance(value, dict):
            raise ValueError("Tool arguments must be an object")
        return value

    def public_description(self, status: CapabilityStatus, setup: str) -> dict[str, Any]:
        """Return UI-safe capability metadata; never includes credentials or prompts."""
        operations = [self.name]
        permission_labels = {
            "https://www.googleapis.com/auth/calendar.readonly": ("Read calendar events and availability"),
            "https://www.googleapis.com/auth/calendar.events": "Create, edit, and delete calendar events",
            "https://www.googleapis.com/auth/calendar": "Full access to Google Calendar",
            "https://www.googleapis.com/auth/gmail.readonly": "Search and read email",
            "https://www.googleapis.com/auth/gmail.compose": "Create and manage unsent drafts",
            "https://www.googleapis.com/auth/gmail.send": "Send email directly or after approval",
            "https://www.googleapis.com/auth/gmail.modify": "Modify email labels, trash, and read/write messages",
            "https://www.googleapis.com/auth/drive.readonly": "Search and read Google Drive files & Docs",
            "https://www.googleapis.com/auth/drive.file": "Create, edit, and delete files managed by this app",
            "https://www.googleapis.com/auth/drive": "Full access to Google Drive",
        }
        return {
            "id": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "provider": self.provider_id,
            "version": self.version,
            "status": status,
            "operations": operations,
            "permission_requirements": list(self.required_permissions),
            "permission_labels": [permission_labels.get(scope, scope) for scope in self.required_permissions],
            "input_schema": self.parameters,
            "output_schema": self.output_schema,
            "connection_required": self.connection_requirement,
            "configuration_guidance": setup,
            "read_only": self.read_only,
            "risk": self.risk,
            "approval_required": self.approval_required,
            "returns_external_urls": self.returns_external_urls,
        }


def _validate_schema(schema: dict[str, Any], value: Any, path: str) -> None:
    """Validate the JSON Schema subset used by model-facing tools, recursively."""
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    if kind is not None:
        checks = {
            "object": lambda v: isinstance(v, dict),
            "array": lambda v: isinstance(v, list),
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "null": lambda v: v is None,
        }
        if not any(candidate in checks and checks[candidate](value) for candidate in kinds):
            raise ValueError(f"{path} has an invalid type")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} has an invalid value")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 1_000_000):
            raise ValueError(f"{path} has an invalid length")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get("minimum", float("-inf")) or value > schema.get("maximum", float("inf")):
            raise ValueError(f"{path} is out of range")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        missing = set(schema.get("required", [])) - set(value)
        if missing:
            raise ValueError(f"Missing argument: {sorted(missing)[0]}")
        extra = set(value) - set(properties)
        if extra and schema.get("additionalProperties", False) is False:
            raise ValueError(f"Unknown argument: {sorted(extra)[0]}")
        for key, item in value.items():
            if key in properties:
                _validate_schema(properties[key], item, f"{path}.{key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                _validate_schema(schema["additionalProperties"], item, f"{path}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 1_000_000):
            raise ValueError(f"{path} has an invalid item count")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                _validate_schema(schema["items"], item, f"{path}[{index}]")


def _check_schema_definition(schema: Any, path: str = "schema") -> None:
    if not isinstance(schema, dict):
        raise ValueError(f"{path} must be an object")
    kind = schema.get("type")
    valid_types = {"object", "array", "string", "integer", "number", "boolean", "null"}
    if kind is not None:
        kinds = kind if isinstance(kind, list) else [kind]
        if not kinds or any(item not in valid_types for item in kinds):
            raise ValueError(f"{path} has an unsupported type")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ValueError(f"{path}.enum must be a non-empty array")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ValueError(f"{path}.properties must be an object")
    required = schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise ValueError(f"{path}.required must be an array of strings")
    if set(required) - set(properties):
        raise ValueError(f"{path}.required must name declared properties")
    for name, child in properties.items():
        _check_schema_definition(child, f"{path}.properties.{name}")
    if isinstance(schema.get("items"), dict):
        _check_schema_definition(schema["items"], f"{path}.items")


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool already registered: {definition.name}")
        if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", definition.name):
            raise ValueError(f"Tool identifier must be namespaced: {definition.name}")
        if definition.parameters.get("type") != "object":
            raise ValueError("Tool input schema must have object type")
        _check_schema_definition(definition.parameters)
        _check_schema_definition(definition.output_schema)
        self._tools[definition.name] = definition

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def discover(self, allowed: set[str] | None = None) -> list[dict[str, Any]]:
        return [
            item.model_description()
            for name, item in sorted(self._tools.items())
            if item.enabled and (allowed is None or name in allowed)
        ]

    def definitions(self) -> list[ToolDefinition]:
        return [item for _, item in sorted(self._tools.items()) if item.enabled]


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
    provider_id: str | None = None,
    category: str | None = None,
    output_schema: dict[str, Any] | None = None,
    input_sensitivity: Literal["public", "personal", "sensitive"] | None = None,
    output_sensitivity: Literal["public", "personal", "sensitive"] | None = None,
    returns_external_urls: bool | None = None,
    enabled: bool = True,
) -> None:
    inferred_provider = (
        "google"
        if name.startswith(("gmail.", "calendar.", "drive."))
        else "telegram"
        if name.startswith("telegram.")
        else "research"
        if name == "research.search"
        else "followthrough"
        if owner == "followthrough"
        else "local"
    )
    inferred_category = (
        "calendar"
        if name.startswith("calendar.")
        else "email"
        if name.startswith("gmail.")
        else "drive"
        if name.startswith("drive.")
        else "messaging"
        if name.startswith("telegram.")
        else "research"
        if name.startswith("research.")
        else "planning"
        if owner == "followthrough"
        else "analysis"
    )
    inferred_sensitivity: Literal["public", "personal", "sensitive"] = (
        "sensitive" if inferred_provider == "google" else "personal"
    )
    if name == "research.search":
        inferred_output_sensitivity: Literal["public", "personal", "sensitive"] = "public"
        inferred_urls = True
    else:
        inferred_output_sensitivity = inferred_sensitivity
        inferred_urls = False
    registry.register(
        ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            owner=owner,
            read_only=read_only,
            approval_required=approval_required,
            timeout_seconds=timeout_seconds,
            retryable=retryable,
            risk=risk,
            connection_requirement=connection_requirement,
            required_permissions=required_permissions,
            provider_id=provider_id or inferred_provider,
            category=category or inferred_category,
            output_schema=output_schema or {"type": "object"},
            input_sensitivity=input_sensitivity or inferred_sensitivity,
            output_sensitivity=output_sensitivity or inferred_output_sensitivity,
            returns_external_urls=(inferred_urls if returns_external_urls is None else returns_external_urls),
            enabled=enabled,
        )
    )
