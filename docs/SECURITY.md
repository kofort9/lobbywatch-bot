# Security Overview

Current security posture, required operator actions, and references.

## Current Posture (Code)

- Slack HTTP endpoints enforce signing-secret verification (raw body hashing, 5-minute window); production fails closed if `SLACK_SIGNING_SECRET` is missing.
- Flask routes default to `bot.slack_app.SlackApp` handlers (admin checks, confirmations, watchlist flows) to avoid drift; legacy handlers remain only for tests/local fallback.
- Permission checks fail closed (`bot/permissions.py`) to avoid accidental allow on errors.
- `.env` is ignored; `.env.example` contains placeholders for all required secrets.

## Immediate Actions (Operators)

- Rotate sensitive credentials if not already rotated:
  - `DATABASE_URL`
  - `SLACK_BOT_TOKEN`
  - `SLACK_SIGNING_SECRET`
  - `SLACK_WEBHOOK_URL`
  - `LDA_API_KEY`
  - `CONGRESS_API_KEY`
  - `REGULATIONS_GOV_API_KEY`
- Update all environments after rotation: GitHub Secrets, Railway (or hosting env), local `.env`.
- Verify `SLACK_SIGNING_SECRET` is set everywhere; production will reject requests without it.
- Optionally clean git history if coordination allows (see `SECURITY_CLEANUP.md`).

## History & Cleanup

- Credentials were present in git history before cleanup; see `SECURITY_CLEANUP.md` for the exposure list and git rewrite instructions (`git-filter-repo`/BFG).
- If history is not rewritten, rotation of all listed credentials is required (above).

## Testing

- Security-focused: `pytest tests/test_web_server_security.py`
- Full suite: `pytest`

## References

- `SECURITY_CLEANUP.md` — exposure history and git rewrite guidance.
- `docs/TECHNICAL_DEBT.md` — remaining security and platform gaps.
