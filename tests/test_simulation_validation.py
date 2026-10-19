from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.simulation import Change, Scenario, SimulationRequest, simulate


def _request(**overrides):
    values = {
        "starting_savings": Decimal("1000"),
        "monthly_income": Decimal("500"),
        "monthly_expenses": Decimal("300"),
        "months": 3,
        "scenarios": [Scenario(name="base")],
    }
    values.update(overrides)
    return SimulationRequest(**values)


@pytest.mark.parametrize("months", [0, -1, 121])
def test_month_count_is_bounded(months):
    with pytest.raises(ValidationError):
        _request(months=months)


@pytest.mark.parametrize("field", ["starting_savings", "monthly_income", "monthly_expenses"])
def test_cash_inputs_reject_negative_values(field):
    with pytest.raises(ValidationError):
        _request(**{field: Decimal("-0.01")})


def test_scenario_count_must_be_between_one_and_twenty():
    with pytest.raises(ValidationError):
        _request(scenarios=[])
    with pytest.raises(ValidationError):
        _request(scenarios=[Scenario(name=f"s{i}") for i in range(21)])


def test_changes_apply_only_at_selected_month_for_one_time_change():
    request = _request(
        months=3,
        scenarios=[
            Scenario(
                name="purchase",
                changes=[Change(name="repair", amount=Decimal("-250"), month=2)],
            )
        ],
    )

    result = simulate(request).scenarios[0]
    assert result.balances == [
        Decimal("1000"),
        Decimal("1200"),
        Decimal("1150"),
        Decimal("1350"),
    ]


def test_minimum_balance_flags_only_months_below_limit():
    request = _request(
        starting_savings=Decimal("100"),
        monthly_income=Decimal("0"),
        monthly_expenses=Decimal("40"),
        months=3,
        minimum_balance=Decimal("50"),
    )

    result = simulate(request).scenarios[0]
    assert result.constraint_violations == [2, 3]
