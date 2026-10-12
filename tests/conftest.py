"""Force the API suite onto isolated local settings, regardless of a developer's .env."""

import os

os.environ["APP_ENV"] = "development"
os.environ["AUTH_MODE"] = "development"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_life_sandbox.db"
os.environ["LLM_PROVIDER"] = "mock"
