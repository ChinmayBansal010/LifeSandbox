from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

DECISION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "compare_allocations",
            "description": (
                "Add up numeric allocations for each option and report whether each meets "
                "the available-time limit. Use when a decision compares plans with numeric "
                "time, money, or other nonnegative allocations. This tool validates arithmetic; "
                "you must interpret the criteria and write the recommendation yourself."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "available_total": {"type": "number", "exclusiveMinimum": 0},
                    "unit": {"type": "string", "description": "For example, minutes or hours."},
                    "options": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "allocations": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "category": {"type": "string"},
                                            "amount": {"type": "number", "minimum": 0},
                                        },
                                        "required": ["category", "amount"],
                                    },
                                },
                            },
                            "required": ["name", "allocations"],
                        },
                    },
                },
                "required": ["available_total", "unit", "options"],
            },
        },
    }
]

class Allocation(BaseModel):
    category: str = Field(min_length=1)
    amount: Decimal = Field(ge=0)


class Option(BaseModel):
    name: str = Field(min_length=1)
    allocations: list[Allocation]


class CompareAllocations(BaseModel):
    available_total: Decimal = Field(gt=0)
    unit: str = Field(min_length=1)
    options: list[Option] = Field(min_length=1)


def execute_decision_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name != "compare_allocations":
        raise ValueError(f"Unsupported tool: {name}")
    request = CompareAllocations.model_validate(arguments)
    results = []
    for option in request.options:
        total = sum((item.amount for item in option.allocations), Decimal(0))
        categories = sorted({item.category for item in option.allocations})
        results.append(
            {
                "name": option.name,
                "allocation_total": str(total),
                "matches_available_total": total == request.available_total,
                "allocations_by_category": {
                    category: str(
                        sum(
                            (
                                item.amount
                                for item in option.allocations
                                if item.category == category
                            ),
                            Decimal(0),
                        )
                    )
                    for category in categories
                },
            }
        )
    return {
        "available_total": str(request.available_total),
        "unit": request.unit,
        "options": results,
    }
