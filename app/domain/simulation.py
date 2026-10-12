from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Change(BaseModel):
    name: str
    amount: Decimal
    frequency: Literal["one_time", "monthly"] = "one_time"
    month: int = Field(default=1, ge=1)


class Scenario(BaseModel):
    name: str
    changes: list[Change] = Field(default_factory=list)


class SimulationRequest(BaseModel):
    starting_savings: Decimal = Field(ge=0)
    monthly_income: Decimal = Field(ge=0)
    monthly_expenses: Decimal = Field(ge=0)
    months: int = Field(default=12, ge=1, le=120)
    scenarios: list[Scenario] = Field(min_length=1, max_length=20)
    minimum_balance: Decimal = Decimal("0")

    @model_validator(mode="after")
    def names_unique(self):
        names = [s.name for s in self.scenarios]
        if len(names) != len(set(names)):
            raise ValueError("Scenario names must be unique")
        return self


class ScenarioResult(BaseModel):
    name: str
    balances: list[Decimal]
    ending_balance: Decimal
    constraint_violations: list[int]


class SimulationResult(BaseModel):
    months: int
    scenarios: list[ScenarioResult]
    assumptions: list[str]


def simulate(request: SimulationRequest) -> SimulationResult:
    """Project cash balances using exact decimal arithmetic; month 0 is starting state."""
    results = []
    for scenario in request.scenarios:
        balance = request.starting_savings
        balances = [balance]
        violations: list[int] = []
        for month in range(1, request.months + 1):
            balance += request.monthly_income - request.monthly_expenses
            for change in scenario.changes:
                if change.frequency == "monthly" or change.month == month:
                    balance += change.amount
            balances.append(balance)
            if balance < request.minimum_balance:
                violations.append(month)
        results.append(
            ScenarioResult(
                name=scenario.name,
                balances=balances,
                ending_balance=balance,
                constraint_violations=violations,
            )
        )
    return SimulationResult(
        months=request.months,
        scenarios=results,
        assumptions=[
            "Income and expenses remain constant unless represented by scenario changes.",
            "Changes occur at the start of the specified month.",
        ],
    )
