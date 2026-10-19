# Quality gates

LifeSandbox uses GitHub Actions to check changes before they are merged. The gates are deliberately split so backend, frontend, container, dependency, and security failures are visible independently.

## Backend

The backend job installs the exact dependency set in `uv.lock`, runs Ruff lint and formatting checks, runs Pyright, and executes the pytest suite with strict configuration and marker handling. The repository hygiene script detects common accidentally committed credentials and runtime artifacts.

Run the same checks locally from the repository root:

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -ra --strict-markers --strict-config
python scripts/check_repo_hygiene.py
```

The new property-based cash-flow tests exercise a range of values rather than a single example. API tests check request bounds and request correlation IDs. Configuration tests ensure production authentication and provider credentials are not silently omitted.

## Frontend

The frontend job uses Node.js 22.12, installs dependencies from `frontend/package-lock.json` with `npm ci`, and runs the Oxlint and TypeScript/Vite production build. The production dependency audit fails on high-severity advisories.

Run locally:

```bash
cd frontend
npm ci
npm run lint
npm run build
npm audit --omit=dev --audit-level=high
```

## Container and dependency changes

The container job builds the backend image with a fresh base-image pull. Pull requests also use GitHub's dependency-review action to flag introduced high-severity dependencies. CodeQL scans Python and TypeScript/JavaScript on pushes to `main`, pull requests targeting `main`, and a weekly schedule. Dependabot proposes weekly updates for Actions, npm, and Python dependencies.

## Local pre-commit hooks

Install the hooks once with `pre-commit install`. Before committing, run all hooks with `pre-commit run --all-files`. These hooks help catch formatting problems, invalid YAML/TOML/JSON, conflict markers, and whitespace defects before CI.

## Interpreting failures

A dependency audit can fail because an upstream package advisory was published after the lockfile was generated; review the advisory and update the affected dependency instead of suppressing the gate. The CodeQL workflow requires GitHub code-scanning support for the repository. Repository settings and organization policy may affect whether security results can be published.
