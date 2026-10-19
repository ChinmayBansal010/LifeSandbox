import pytest
from pydantic import ValidationError
from app.domain.simulation import SimulationRequest, Change

def test_simulation_rejects_zero_month_horizon():
    with pytest.raises(ValidationError):
        SimulationRequest(starting_savings=0, monthly_income=0, monthly_expenses=0, months=0, scenarios=[{"name":"base"}])

def test_simulation_rejects_more_than_twenty_scenarios():
    with pytest.raises(ValidationError):
        SimulationRequest(starting_savings=0, monthly_income=0, monthly_expenses=0, scenarios=[{"name":f"s{i}"} for i in range(21)])

def test_change_month_must_be_positive():
    with pytest.raises(ValidationError):
        Change(name="repair", amount=-10, month=0)

def test_negative_starting_savings_is_rejected():
    with pytest.raises(ValidationError):
        SimulationRequest(starting_savings=-1, monthly_income=0, monthly_expenses=0, scenarios=[{"name":"base"}])

def test_one_time_change_outside_projection_is_rejected():
    with pytest.raises(ValidationError, match="outside"):
        SimulationRequest(
            starting_savings=0,
            monthly_income=0,
            monthly_expenses=0,
            months=2,
            scenarios=[{"name":"base","changes":[{"name":"future cost","amount":-10,"month":3}]}],
        )

def test_whitespace_only_change_name_is_rejected():
    with pytest.raises(ValidationError, match="blank"):
        Change(name="   ", amount=-10)

def test_scenario_name_is_trimmed():
    request = SimulationRequest(
        starting_savings=0,
        monthly_income=0,
        monthly_expenses=0,
        scenarios=[{"name":"  baseline  "}],
    )
    assert request.scenarios[0].name == "baseline"
