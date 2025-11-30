# Test Coverage & Validation

Lightweight guide for measuring and improving test coverage while new features (email, dashboard APIs) are added.

## Current Snapshot (full suite)
- Last full run: `pytest --cov=bot --cov-report=term-missing` → **64% overall** (2025-02-XX).
- **Highest coverage**: `bot/notifiers/email.py` (100%), `bot/notifiers/slack.py` (100%), `bot/database_postgres.py` (100%), `bot/signals.py` (85%), `bot/utils.py` (92%), `bot/web_server.py` (85%), `bot/database.py` (78%)
- **Remaining low coverage (post-new tests)**:
  - `bot/enhanced_run.py`: 41% — CLI/server paths still untested (86 lines untested)
  - `bot/lda_scheduler.py`: 48% — ETL internals still uncovered (34 lines untested)
  - `bot/slack_app.py`: 56% — LDA error paths, permission denials, alert helpers remain (166 lines untested)
  - `bot/enhanced_digest.py`: 89% — DB error paths still missing (22 lines untested)
  - `bot/matching.py`: 42% — needs more entity/issue matching edge cases (101 lines untested)
  - `bot/fr_digest.py`: 37% — still lacking formatting edge cases (171 lines untested)
  - `bot/lda_etl.py`: 46% — retry/error handling and ingest logging need coverage (188 lines untested)
  - `bot/run.py`: 72% — notifier selection and CLI paths missing (50 lines untested)
  - `bot/daily_signals.py`: 75% — retry/backoff branches and surge logic missing (133 lines untested)

## Progress & Remaining Gaps

**Progress**: Smoke/edge coverage added for `enhanced_run`, `lda_scheduler`, `slack_app`, and `enhanced_digest` (see `tests/test_enhanced_run.py`, `tests/test_enhanced_run_additional.py`, `tests/test_lda_scheduler.py`, `tests/test_lda_scheduler_additional.py`, `tests/test_slack_app_enhanced.py`, `tests/test_enhanced_digest.py`). These modules are no longer at 0–19% and overall coverage is now 64% (+7 points from the 57% baseline).

**Still missing**:
1. Deeper paths and failure modes in `slack_app.py` (LDA subcommands, Slack errors, signature failures).
2. Daily-mode coverage and DB error paths in `enhanced_digest.py`.
3. Broader coverage for `bot/run.py`, `bot/daily_signals.py`, `bot/fr_digest.py`, `bot/lda_etl.py`, and `bot/matching.py` edge cases.
4. Avoid test duplication; prioritize uncovered branches and error handling toward the 70% goal.

## How to Measure
- Full suite with coverage:
  ```bash
  pytest --cov=bot --cov-report=term-missing
  ```
- Narrow focus (faster while iterating):
  ```bash
  pytest tests/test_run.py tests/test_notifiers_email.py --cov=bot --cov-report=term-missing
  ```
- Check specific module coverage:
  ```bash
  pytest --cov=bot --cov-report=term-missing | grep "bot/enhanced_run"
  ```

## Priority Gaps (high impact, low coverage)
- `bot/run.py` and `bot/daily_signals.py`: core control flow, API fetching, thresholds.
- `bot/web_server.py`: slash command/event handlers and error paths.
- `bot/signals_database.py`: persistence, stats, and watchlist stubs.
- `bot/notifiers/`: Slack and email send paths (happy + failure cases).

### Per-file snapshot (latest full run)
| File | Coverage* | Notes |
| --- | --- | --- |
| `bot/enhanced_run.py` | 41% | Smoke tests added; CLI/server execution paths remain. |
| `bot/lda_scheduler.py` | 48% | Scheduler happy/error cases covered; ETL internals untested. |
| `bot/slack_app.py` | 56% | Slash command, confirmations, signature checks covered; LDA error paths still open. |
| `bot/enhanced_digest.py` | 89% | Formatting/mini/daily digest covered; DB error handling open. |
| `bot/matching.py` | ~42% | Needs more edge cases and issue/entity matching permutations. |
| `bot/fr_digest.py` | ~37% | Formatting edge cases and surge logic remain. |
| `bot/run.py` | 72% | Notifier selection and CLI options still missing. |
| `bot/daily_signals.py` | 75% | Retry/backoff branches and surge logic still untested. |
| `bot/signals_database.py` | 64% | Persistence/statistics/watchlist stubs need coverage. |

_*Coverage numbers come from the latest full-suite run noted above._

## Near-Term Targets (small wins)
- ✅ **COMPLETED**: Add end-to-end tests for the V2 path: collect signals → format digest → send via email notifier (mock SMTP). See `tests/test_v2_e2e.py`.
- ✅ **COMPLETED**: Cover `/lobbypulse` and `/threshold` handlers for watchlist/threshold persistence. See `tests/test_web_server.py` (enhanced with new tests).
- ✅ **COMPLETED**: Add failure-mode tests for Congress/FR/Regs API clients with timeouts/retries. See `tests/test_api_failure_modes.py`.
- ✅ **COMPLETED**: Add a smoke test for the upcoming FastAPI `/api/signals` and `/api/watchlist` endpoints. See `tests/test_api_endpoints_smoke.py` (placeholder tests documenting expected behavior).
- ✅ **COMPLETED**: Add tests for `bot/permissions.py` (73% coverage) - permission checking, caching, API error handling. See `tests/test_permissions.py`.
- ✅ **COMPLETED**: Add tests for `bot/matching.py` (42% coverage) - fuzzy matching, string normalization, entity matching. See `tests/test_matching.py`.
- ✅ **COMPLETED**: Add tests for `bot/database_postgres.py` (100% coverage) - PostgreSQL connection, schema creation, factory function. See `tests/test_database_postgres.py`.
- ✅ **COMPLETED**: Add smoke/edge tests for `bot/enhanced_run.py`, `bot/lda_scheduler.py`, `bot/slack_app.py`, and `bot/enhanced_digest.py` (see new tests under `tests/`).

## Validation Practices (as we build)
- For every feature PR: run `pytest --cov=bot --cov-report=term-missing` (or at least the affected test subset) and note the result. After the new tests, rerun the full suite to update the baseline %.
- Keep a plain-text fallback for HTML emails and validate both parts in tests.
- Use fixtures/mocking for external APIs and SMTP/Slack to avoid network calls.
- Add regression tests for any bug fix before merging.
- **Before adding new tests**: Check which modules have the lowest coverage and prioritize those.

## When to Update This Doc
- After running the full suite, replace the snapshot with the real overall % and key per-file notes.
- Record any coverage threshold you want to gate in CI (e.g., `--cov-fail-under=30` once feasible).
- Update when new low-coverage modules are identified or when coverage targets are reached.
