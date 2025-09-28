# 🔍 LobbyLens

A daily messaging bot that summarizes fresh U.S. lobbying activity from OpenSecrets and ProPublica APIs, sending concise digests via Slack.

![Tests](https://github.com/your-username/lobbylens/workflows/Tests%20and%20Code%20Quality/badge.svg)
![Daily Digest](https://github.com/your-username/lobbylens/workflows/LobbyLens%20Daily%20Digest/badge.svg)

## Features

- 📋 **Daily Digest**: New filings, top registrants, and issue activity trends
- 📊 **Smart Analytics**: Week-over-week issue code surge detection  
- 🚀 **Slack Integration**: Clean, formatted messages with direct links
- ⚙️ **Automated**: Runs daily via GitHub Actions at 8:00 AM PT
- 🔒 **Secure**: API keys and webhooks stored as GitHub secrets
- 🧪 **Well Tested**: Comprehensive test suite with 90%+ coverage

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/your-username/lobbylens.git
cd lobbylens
pip install -e ".[dev]"
```

### 2. Set Up Environment

```bash
cp .env.example .env
# Edit .env with your API keys and Slack webhook
```

### 3. Configure Slack

1. Create a Slack app at https://api.slack.com/apps
2. Add an "Incoming Webhook" to your desired channel
3. Copy the webhook URL to your `.env` file

### 4. Get API Keys

- **OpenSecrets**: Register at https://www.opensecrets.org/api/admin/index.php?function=signup
- **ProPublica**: Get a key at https://www.propublica.org/datastore/api/propublica-congress-api

### 5. Run Locally

```bash
# Test with dry run (no actual notification)
lobbylens --dry-run

# Run normally (sends to Slack)
lobbylens

# Skip data fetching (use existing database)
lobbylens --skip-fetch
```

## GitHub Actions Setup

### Required Secrets

Add these secrets in your GitHub repository settings (`Settings > Secrets and variables > Actions`):

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | ✅ Yes |
| `OPENSECRETS_API_KEY` | OpenSecrets API key | ⚠️ Recommended |
| `PROPUBLICA_API_KEY` | ProPublica Congress API key | ⚠️ Recommended |

### Workflows

- **Daily Digest** (`.github/workflows/daily.yml`): Runs at 8:00 AM PT daily
- **Testing** (`.github/workflows/test.yml`): Runs on every push/PR

### Manual Triggers

You can manually trigger the daily digest from the GitHub Actions tab using "Run workflow".

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_FILE` | `lobbywatch.db` | SQLite database path |
| `SLACK_WEBHOOK_URL` | - | Slack webhook URL (required) |
| `OPENSECRETS_API_KEY` | - | OpenSecrets API key |
| `PROPUBLICA_API_KEY` | - | ProPublica API key |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARN, ERROR) |
| `DRY_RUN` | `false` | Generate digest without sending |

### CLI Options

```bash
lobbylens --help

Options:
  --dry-run         Generate digest but don't send notification
  --skip-fetch      Skip data fetching, only generate digest
  --log-level TEXT  Set logging level [DEBUG|INFO|WARNING|ERROR]
  --help           Show this message and exit
```

### Slack Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `/lobbypulse` | Generate fresh lobbying digest | `/lobbypulse [daily\|mini\|help]` |
| `/watchlist` | Manage watchlist entities | `/watchlist add\|remove\|list [name]` |
| `/threshold` | Set alert thresholds | `/threshold set [number]` |
| `/summary` | Toggle digest descriptions | `/summary set [on\|off]` |
| `/lobbylens` | General bot help | `/lobbylens [help]` |

## Sample Output

```
🔍 LobbyLens Daily Digest — 2024-10-15

📋 New filings (last 24h):
• Acme Corp → K Street Advisors ($50K) • <http://example.com/filing1|View>
• BigTech Inc → Capitol Consulting ($75K)
• MegaPharm LLC → Influence Partners ($100K)

💰 Top registrants (7d):
• Capitol Consulting: $225K (5 filings)
• K Street Advisors: $150K (3 filings)
• Influence Partners: $100K (2 filings)

📈 Issue activity (7d vs prior 7d):
• HCR: 8 filings (prev 3) +167%
• TAX: 5 filings (prev 0) ∞
• DEF: 12 filings (prev 10) +20%

Updated at 15:00 UTC
```

## Development

### Prerequisites

- Python 3.10+
- SQLite3
- Git

### Setup

```bash
# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run tests with coverage
pytest --cov=bot --cov-report=html

# Format code
black bot tests
isort bot tests

# Type checking
mypy bot

# Lint
flake8 bot tests
```

### Testing

The test suite includes:

- **Unit tests**: All modules with >90% coverage
- **Integration tests**: End-to-end CLI testing  
- **Mock testing**: External API calls and notifications
- **Snapshot testing**: Digest format validation

```bash
# Run all tests
pytest -v

# Run specific test files
pytest tests/test_digest.py -v

# Run with debugging
pytest -v -s --pdb
```

### Project Structure

```
lobbylens/
├── bot/                    # Main package
│   ├── __init__.py
│   ├── config.py          # Settings and environment
│   ├── digest.py          # Daily digest computation
│   ├── run.py             # CLI entry point
│   └── notifiers/         # Notification providers
│       ├── __init__.py
│       ├── base.py        # Base protocol
│       └── slack.py       # Slack implementation
├── tests/                 # Test suite
│   ├── conftest.py       # Pytest fixtures
│   ├── test_*.py         # Test modules
│   └── snapshots/        # Expected outputs
├── state/                # Runtime state files
├── .github/workflows/    # GitHub Actions
│   ├── daily.yml        # Daily digest runner
│   └── test.yml         # CI/CD pipeline
├── pyproject.toml       # Project configuration
├── .env.example         # Environment template
└── README.md           # This file
```

## Database Schema

LobbyLens expects a SQLite database with the following schema (compatible with [lobbywatch](https://github.com/your-username/lobbywatch)):

```sql
-- Core entities (clients, registrants)
entity(id, name, type)

-- Issue codes (HCR, TAX, DEF, etc.)
issue(id, code, description)

-- Filing records
filing(id, client_id, registrant_id, filing_date, created_at, amount, url, description)

-- Filing-issue relationships (many-to-many)
filing_issue(id, filing_id, issue_id)
```

## Troubleshooting

### Common Issues

**No notifications received:**
- Check Slack webhook URL is correct
- Verify webhook has proper channel permissions
- Check GitHub Actions logs for errors

**Database not found:**
- Ensure `lobbywatch` package is installed
- Run initial data fetch manually
- Check `DATABASE_FILE` path

**API rate limits:**
- OpenSecrets: 200 requests/day
- ProPublica: 5000 requests/day
- Consider reducing fetch limits in code

**Memory issues:**
- SQLite database can grow large over time
- Consider periodic cleanup of old records
- Archive state files regularly

### Debug Mode

```bash
# Enable verbose logging
export LOG_LEVEL=DEBUG
lobbylens --dry-run

# Check digest computation only
python -c "from bot.digest import compute_digest; print(compute_digest('lobbywatch.db'))"

# Test Slack notification
python -c "from bot.notifiers.slack import SlackNotifier; SlackNotifier('YOUR_WEBHOOK').send('Test message')"
```

### GitHub Actions Debug

- Check the Actions tab for workflow runs
- Download artifacts (database files) for inspection
- Use workflow dispatch for manual testing
- Check repository secrets are properly set

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and add tests
4. Run the full test suite: `pytest`
5. Ensure code quality: `black . && isort . && flake8`
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [OpenSecrets.org](https://www.opensecrets.org/) for lobbying data API
- [ProPublica](https://www.propublica.org/) for Congress API
- Built on the `lobbywatch` data processing foundation