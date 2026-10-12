from decimal import Decimal

import pytest

from app.domain.simulation import Change, Scenario, SimulationRequest, simulate


def test_projection_is_exact_and_tracks_constraint_violations():
    request = SimulationRequest(
        starting_savings=Decimal("1000"),
        monthly_income=Decimal("500"),
        monthly_expenses=Decimal("600"),
        months=3,
        minimum_balance=Decimal("500"),
        scenarios=[
            Scenario(name="base"),
            Scenario(
                name="laptop", changes=[Change(name="laptop", amount=Decimal("-800"), month=1)]
            ),
        ],
    )
    result = simulate(request)
    assert result.scenarios[0].balances == [
        Decimal("1000"),
        Decimal("900"),
        Decimal("800"),
        Decimal("700"),
    ]
    assert result.scenarios[1].constraint_violations == [1, 2, 3]


def test_monthly_change_applies_each_month():
    request = SimulationRequest(
        starting_savings=Decimal("0"),
        monthly_income=Decimal("0"),
        monthly_expenses=Decimal("0"),
        months=2,
        scenarios=[
            Scenario(
                name="stipend",
                changes=[Change(name="stipend", amount=Decimal("50"), frequency="monthly")],
            )
        ],
    )
    assert simulate(request).scenarios[0].ending_balance == Decimal("100")


def test_invalid_scenario_names_rejected():
    with pytest.raises(ValueError):
        SimulationRequest(
            starting_savings=0,
            monthly_income=0,
            monthly_expenses=0,
            scenarios=[Scenario(name="same"), Scenario(name="same")],
        )
