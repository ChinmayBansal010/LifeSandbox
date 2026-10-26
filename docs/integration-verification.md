# Optional Integration Verification

**Date:** 2026-10-17 (Updated: 2026-10-26)

## Environment

- Fedora host, Python 3.13, Docker Compose PostgreSQL/API/worker stack.
- Mem0 API key was configured but is not recorded here. The per-user `hosted_memory_allowed` setting was temporarily enabled for verification and restored to `false` afterward.
- Docker API image is updated to include the optional `browser` extra (`uv sync --locked --no-dev --extra browser`) and Debian Chromium runtime (`/usr/bin/chromium`).
- The host Python integration is installed with `uv sync --locked --extra browser`. `find_browser_executable()` auto-discovers `/usr/bin/chromium`, `/usr/bin/google-chrome`, `CHROME_PATH`, or system PATH.

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

- **Container Image & Capability Detection (Resolved):**
  - Added Debian `chromium`, `fonts-liberation`, and `ca-certificates` to `Dockerfile`, with `CHROME_BIN=/usr/bin/chromium` and `CHROME_PATH=/usr/bin/chromium`.
  - Added the `browser` extra (`uv sync --locked --no-dev --extra browser`) to the Docker build step.
  - Added `shm_size: '1gb'` to the `api` service in `docker-compose.yml` to prevent Chromium tab crashes in Docker.
  - Added `find_browser_executable()` to verify browser binary existence before reporting `is_configured() = True`. If the binary or module is missing, `/api/v1/capabilities` truthfully reports `browser_use_enabled: false` and `POST /api/v1/chat` returns HTTP 503 `browser_use_not_configured`.
  - With `BROWSER_USE_ENABLED=true` and LLM credentials supplied, the container reports Browser Use as ready (`browser_use_enabled: true`), and composer switches reflect active status.
- **Safety Constraints Verified:**
  - Browser executes under unprivileged container user `appuser` (uid 10001).
  - Uses isolated temporary profiles per turn (`/tmp/life-sandbox-browser-use`).
  - No authenticated browser profiles or persistent cookies are accepted.
  - Downloads are strictly disabled (`accept_downloads=False`).
  - Navigation is bounded to `github.com` (`allowed_domains=["github.com"]`).
- **Repository-page opening and citation verification (Resolved):**
  - Added deterministic end-to-end fixture and execution trace (`test_browser_research_repository_page_and_citations_e2e`) verifying that valid repository links (e.g. `https://github.com/Xilinx/Vitis-AI`) are selected from search results, opened directly in the browser session, have their project, license (`Apache-2.0`), and hardware facts (`ZCU104`) extracted into evidence, and carry the observed repository URL into the final response as a source citation.
  - Reserved GitHub paths (`/features/copilot`, `/login`, `/pricing`) are excluded from repository opening and never cited.
  - When repository pages cannot be verified or research fails, no unverified project, license, or hardware details are emitted (`test_browser_research_failure_returns_no_unverified_claims`).
  - Added an opt-in live test (`test_live_github_browser_research_if_configured`) enabled via `RUN_LIVE_GITHUB_TEST=1` to document real repository research or specific environmental blockers without making CI depend on GitHub availability.

## Composer Accessibility

- The Mem0 and Browser Use switches exposed distinct screen-reader labels and independent checked states.
- Keyboard `Space` toggled Mem0 on and off; Browser Use remained disabled and unchecked.
- The same enabled/disabled states and labels were checked at 1280px and 390px widths.
- The per-message Mem0 switch reset after the send, including the timed-out UI request.

## Remaining Issues

- The OpenRouter UI request timed out before Mem0 save confirmation. Mem0 search/save itself passed on the mock-model retry.

## Milestone 2 implementation checks (2026-10-19)

- Added mocked OAuth authorize/callback coverage, one-time state replay rejection, and verification that access/refresh credentials are encrypted before database persistence.
- Added mocked approval execution coverage for Gmail draft sends, including changed-draft rejection and repeated execution without a second send.
- Added mocked Calendar free/busy analysis and normal-chat research tool executor coverage.
- No live Google account or OAuth client was configured, so Calendar and Gmail were not verified against Google's services. The callback, token refresh, and provider request behavior still require manual verification with a configured Google Cloud project.
- Calendar writes (create/update/cancel) remain unavailable. Gmail send is implemented with an approval snapshot; ambiguous outcomes are marked uncertain and are not retried.
