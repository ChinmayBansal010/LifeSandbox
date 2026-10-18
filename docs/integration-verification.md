# Optional Integration Verification

**Date:** 2026-10-17

## Environment

- Fedora host, Python 3.13, Docker Compose PostgreSQL/API/worker stack.
- Mem0 API key was configured but is not recorded here. The per-user `hosted_memory_allowed` setting was temporarily enabled for verification and restored to `false` afterward.
- Docker API image did not contain `browser_use`; `BROWSER_USE_ENABLED=true` alone did not make the integration available.
- The optional `browser` extra was installed into the host `.venv` with `uv sync --locked --extra browser`. The declared `uv run browser-use install` command attempted Ubuntu/apt system-dependency setup and failed because this host has no `apt-get`. `/usr/bin/google-chrome` was present.

## Mem0

- Composer showed **Ready** with the key configured. The per-message switch was turned on for a synthetic, non-sensitive prompt.
- The UI request reached Mem0 search successfully (`POST /v3/memories/search/`, HTTP 200), but its OpenRouter response did not finish. The frontend timed out at 105 seconds; logs later showed `Model provider failure provider=openrouter status_code=None`. The UI displayed “Mem0 did not confirm saving this exchange” and reset the one-message switch.
- A retry through the same chat service with `LLM_PROVIDER=mock` and the real Mem0 adapter completed: Mem0 search and add both returned HTTP 200, and the API returned `memory_saved: true`.

### Timeout and Mem0 save status contract

The OpenRouter request previously could outlive the browser's 105-second abort. The browser then reported an unconfirmed Mem0 save even when the LLM had failed before the save stage. OpenRouter now has a 75-second budget, Mem0 search and add each have 10-second budgets, and the overall chat server budget is 95 seconds (frontend safety timeout remains 105 seconds). Configure these with `OPENROUTER_TIMEOUT_SECONDS`, `MEM0_SEARCH_TIMEOUT_SECONDS`, `MEM0_ADD_TIMEOUT_SECONDS`, and `CHAT_REQUEST_TIMEOUT_SECONDS`.

Chat results report `mem0_opt_in`, `mem0_search_status`, `mem0_save_status`, and `failure_detail`. A model failure reports `not_attempted`; only a confirmed Mem0 add reports `saved`. Verify by opting in with a slow/unavailable OpenRouter model (no add should run), then with `LLM_PROVIDER=mock` and a working Mem0 service (save reports `saved`).
- The local synthetic conversation was deleted and hosted-memory policy was restored to disabled. The synthetic exchange remains in the external Mem0 account because this adapter has no memory-delete operation.
- With `MEM0_API_KEY` blank in the process environment, `is_configured()` returned false. A temporary browser capabilities override produced two **Setup required** cards with both switches disabled; the override was removed and the real page reloaded.

## Browser Use

- The Docker API reported `browser_use_enabled: false`; the composer showed **Setup required** and a disabled switch. `POST /api/v1/chat` with `browse: true` returned HTTP 503 with `browser_use_not_configured`.
- The host Python integration became configured after installing the optional extra. Its browser source uses a temporary profile, disables default extensions, sets `accept_downloads=false`, and restricts navigation to `github.com`; no authenticated profile or download was enabled.
- Live local-Chrome searches opened GitHub search URLs but returned no repository results for `python`, `octocat/Hello-World`, and `ChinmayBansal010 LifeSandbox`. The first run exposed a false positive where `/features/copilot` was treated as a repository. The parser now rejects reserved GitHub paths and explicit zero-result pages; regression tests cover this case.
- With no repository links, chat returned the explicit response that research could not be completed and that project/license/hardware details were unverified. The trace showed a browser-research error and no LLM completion. A regression test verifies this path.
- Repository-page opening and source citation were **not verified**, because GitHub search returned no repositories in this environment. The report does not claim a successful live research answer.

## Composer Accessibility

- The Mem0 and Browser Use switches exposed distinct screen-reader labels and independent checked states.
- Keyboard `Space` toggled Mem0 on and off; Browser Use remained disabled and unchecked.
- The same enabled/disabled states and labels were checked at 1280px and 390px widths.
- The per-message Mem0 switch reset after the send, including the timed-out UI request.

## Remaining Issues

- The Docker image still excludes the optional Browser Use dependency and Chromium; it therefore continues to show Browser Use as unavailable. The host package installation does not alter Docker or tracked dependency files.
- GitHub search returned zero repositories from this network/browser session, so a successful repository-page citation flow remains unverified.
- The OpenRouter UI request timed out before Mem0 save confirmation. Mem0 search/save itself passed on the mock-model retry.
