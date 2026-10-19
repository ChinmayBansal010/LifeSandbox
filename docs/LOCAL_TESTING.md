# Local testing

Run the full Python test suite from the repository root:

```bash
uv run pytest
```

Run one area while iterating:

```bash
uv run pytest tests/test_life.py -q
uv run pytest tests/test_tool_registry.py tests/test_tool_registry_edge_cases.py -q
uv run ruff check app tests
uv run pyright
```

Build and lint the frontend:

```bash
cd frontend
npm ci
npm run build
npm run lint
```

Tests that create database rows should use the existing test fixtures and clean up state when appropriate. A successful typecheck or unit test does not establish provider quality or prove a third-party integration works in production.
