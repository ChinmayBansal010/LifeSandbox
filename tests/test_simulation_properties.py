from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.simulation import Scenario, SimulationRequest, simulate


@given(
    starting=st.integers(min_value=0, max_value=10_000_000),
    income=st.integers(min_value=0, max_value=100_000),
    expenses=st.integers(min_value=0, max_value=100_000),
    months=st.integers(min_value=1, max_value=24),
)
@settings(max_examples=60, deadline=None)
def test_baseline_projection_matches_monthly_cash_flow(starting, income, expenses, months):
    request = SimulationRequest(
        starting_savings=Decimal(starting),
        monthly_income=Decimal(income),
        monthly_expenses=Decimal(expenses),
        months=months,
        scenarios=[Scenario(name="baseline")],
    )

    result = simulate(request).scenarios[0]
    expected = Decimal(starting) + (Decimal(income) - Decimal(expenses)) * months

    assert result.ending_balance == expected
    assert len(result.balances) == months + 1
    assert result.balances[0] == Decimal(starting)
    assert result.balances[-1] == result.ending_balance


@given(
    starting=st.integers(min_value=0, max_value=1_000_000),
    monthly_delta=st.integers(min_value=-10_000, max_value=10_000),
    months=st.integers(min_value=1, max_value=24),
)
@settings(max_examples=60, deadline=None)
def test_projection_uses_exact_decimal_arithmetic(starting, monthly_delta, months):
    request = SimulationRequest(
        starting_savings=Decimal(starting),
        monthly_income=Decimal(max(monthly_delta, 0)),
        monthly_expenses=Decimal(max(-monthly_delta, 0)),
        months=months,
        scenarios=[Scenario(name="baseline")],
    )

    result = simulate(request).scenarios[0]
    assert result.ending_balance == Decimal(starting) + Decimal(monthly_delta) * months
