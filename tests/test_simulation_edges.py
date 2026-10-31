import pytest
from pydantic import ValidationError

from app.domain.simulation import SimulationRequest, simulate


def test_month_zero_is_starting_balance_and_each_month_is_recorded():
    request = SimulationRequest(
        starting_savings="125.50", monthly_income="10", monthly_expenses="5", months=3, scenarios=[{"name": "base"}]
    )
    result = simulate(request).scenarios[0]
    assert result.balances == [125.50, 130.50, 135.50, 140.50]
    assert result.ending_balance == 140.50


def test_monthly_change_applies_each_month():
    request = SimulationRequest(
        starting_savings=0,
        monthly_income=0,
        monthly_expenses=0,
        months=3,
        scenarios=[{"name": "base", "changes": [{"name": "subscription", "amount": "-12.50", "frequency": "monthly"}]}],
    )
    result = simulate(request).scenarios[0]
    assert result.balances == [0, -12.5, -25, -37.5]


def test_constraint_violations_are_reported_by_month():
    request = SimulationRequest(
        starting_savings=20,
        monthly_income=0,
        monthly_expenses=8,
        months=3,
        minimum_balance=5,
        scenarios=[{"name": "base"}],
    )
    result = simulate(request).scenarios[0]
    assert result.constraint_violations == [2, 3]


def test_duplicate_scenario_names_are_rejected():
    with pytest.raises(ValidationError, match="unique"):
        SimulationRequest(
            starting_savings=0, monthly_income=0, monthly_expenses=0, scenarios=[{"name": "base"}, {"name": "base"}]
        )
