# 🔍 LobbyLens

A two-layer government monitoring system providing daily government activity signals and quarterly lobbying analysis.

## 🏗️ **Two-Layer Architecture**

### **V2: Daily Activity Layer** (Currently Active)
- **Data Source**: Government APIs (Congress, Federal Register, Regulations.gov)
- **Purpose**: Track what the government is doing daily
- **Content**: Bills, hearings, regulations, regulatory actions
- **Deployment**: Railway (main.py) + Docker (updated)

### **V1: Quarterly Money Layer** (Prepared for Future)
- **Data Source**: Lobbying Disclosure Act (LDA) filings
- **Purpose**: Track who's paying whom to lobby, how much, on which issues
- **Content**: Lobbying filings, clients, registrants, amounts, issue codes
- **Status**: Prepared for future LDA implementation

> **📋 Architecture Note**: The system has evolved to separate daily government activity monitoring (V2) from quarterly lobbying analysis (V1). V2 is currently active and tracks government actions, while V1 is prepared for future LDA data integration.

![Tests](https://github.com/your-username/lobbylens/workflows/Tests%20and%20Code%20Quality/badge.svg)
![Daily Digest](https://github.com/your-username/lobbylens/workflows/LobbyLens%20Daily%20Digest/badge.svg)

## Features

### V2: Daily Government Activity (Currently Active)
- 📰 **Daily Digest**: Bills, hearings, regulations, and regulatory actions
- 🎯 **Smart Filtering**: Watchlist-based alerts and threshold triggers
- 📊 **Priority Scoring**: Deterministic scoring based on source, timing, and relevance
- 🔍 **Issue Mapping**: Automatic categorization using rule-based mappings
- 📱 **Mobile Formatting**: Character budgets, line breaking, mobile-friendly design
- 🏭 **Industry Snapshots**: Categorized view of government activity by industry

### V1: Quarterly Lobbying Analysis (Prepared for Future)
- 📊 **Quarterly Reports**: Deep analysis of actual lobbying disclosure data
- 🏢 **Client & Registrant Analysis**: Top spenders, new registrations, issue trends
- 📈 **Trend Detection**: Quarter-over-quarter changes in lobbying activity
- 📋 **CSV Exports**: Downloadable data for further analysis

### Platform Features
- 🚀 **Slack Integration**: Clean, formatted messages with direct links
- ⚙️ **Automated Scheduling**: Quarterly reports + daily digests
- 🔒 **Secure**: Environment-based configuration
- 🧪 **Well Tested**: Comprehensive test suite with deterministic logic
- 💬 **Interactive Commands**: Full Slack slash command support

## Data Sources & Cadence

### V2: Daily Government Activity (Active)
- **Congress API**: Bills, votes, hearings, committee actions
- **Federal Register API**: Rules, notices, regulatory actions by agency
- **Regulations.gov API**: Dockets, comment counts, regulatory surges
- **Refresh**: Daily (8 AM PT) + Mini (4 PM PT if thresholds hit)
- **Content**: Government actions, regulatory changes, bill movements

### V1: Quarterly Lobbying Data (Prepared)
- **Source**: Senate/House LDA bulk files (XML/CSV)
- **Refresh**: Quarterly (when new data is published)
- **Content**: Actual lobbying filings, clients, registrants, amounts, issue codes
- **Output**: Comprehensive quarterly reports with CSV exports

## 💬 **Slack Commands**

LobbyLens provides comprehensive Slack integration with interactive slash commands for digest generation, watchlist management, and system configuration.

### **Digest Commands**
- **`/lobbypulse`** - Generate daily digest (24h of government activity)
- **`/lobbypulse mini`** - Generate mini digest (4h, when thresholds met)
- **`/lobbypulse help`** - Show all available commands

### **Watchlist Commands**
- **`/watchlist add <entity>`** - Add entity to watchlist (e.g., `/watchlist add Google`)
- **`/watchlist remove <entity>`** - Remove entity from watchlist
- **`/watchlist list`** - Show current watchlist items

### **Settings Commands**
- **`/threshold set <number>`** - Set mini-digest threshold (e.g., `/threshold set 5`)
- **`/threshold`** - Show current threshold settings

### **System Commands**
- **`/lobbylens`** - Show system status and database statistics
- **`/lobbylens help`** - Show comprehensive system help and features

### **Command Examples**
```bash
# Get daily digest
/lobbypulse

# Get mini digest
/lobbypulse mini

# Add entities to watchlist
/watchlist add Google
/watchlist add Microsoft
/watchlist add "Federal Reserve"

# Set mini-digest threshold
/threshold set 5

# Check system status
/lobbylens

# Get help
/lobbypulse help
```

### **Digest Format**
The daily digest includes:
- **🔎 Watchlist Alerts** - Signals matching your watchlist entities
- **📈 What Changed** - Recent government activity and regulatory changes
- **🏭 Industry Snapshots** - Categorized view by industry (Tech, Health, Energy, etc.)
- **⏰ Deadlines** - Upcoming deadlines and comment periods
- **📊 Docket Surges** - Regulatory dockets with significant activity increases
- **📜 New Bills & Actions** - Recent congressional activity

## 🚀 **Recent Migration (September 2025)**

### What Changed
- **Unified Deployment**: Both Railway and Docker now use V2 system
- **Cleaned Codebase**: Removed obsolete V1 files that were superseded by V2
- **Two-Layer Architecture**: Separated daily government activity from quarterly lobbying analysis
- **Simplified Maintenance**: Single active system (V2) with V1 prepared for future use

### Files Removed
- `bot/web_server_v2.py` - Redundant with `web_server.py`
- `bot/run_v2.py` - Not used in deployment
- `bot/digest.py` - Superseded by `digest_v2.py`
- `bot/signals_database.py` - Superseded by `signals_database_v2.py`
- `bot/daily_signals.py` - Superseded by `daily_signals_v2.py`
- `bot/signals_digest.py` - Superseded by `digest_v2.py`
- `bot/daily_signals_cli.py` - Superseded by main run modules
- `README_V2.md` - Consolidated into main README
- `lobbywatch.db` - V1 database file

### Files Kept (V1 Money Layer)
- `bot/enhanced_run.py` - V1 entry point for lobbying data
- `bot/enhanced_digest.py` - V1 digest for lobbying data
- `bot/slack_app.py` - V1 Slack integration
- `bot/matching.py` - V1 fuzzy matching for lobbying entities
- `bot/database.py` - V1 database for lobbying data
- `bot/database_postgres.py` - V1 PostgreSQL support

### Issue Mapping (No AI)
- **Agency → Issue Codes**: FCC→TEC, HHS→HCR, etc.
- **Committee → Issue Codes**: Finance→FIN, Energy & Commerce→ENE/TEC
- **Bill Keywords → Issue Codes**: Deterministic keyword mapping
- **Priority Scoring**: Rule-based scoring with configurable weights

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

- **Congress API**: Get a key at https://api.congress.gov/sign-up/
- **Federal Register**: No API key required (free service)
- **Regulations.gov**: Get a key at https://open.gsa.gov/api/regulationsgov/

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
| `SLACK_BOT_TOKEN` | Slack bot token for enhanced features | ✅ Yes |
| `SLACK_SIGNING_SECRET` | Slack signing secret for request verification | ✅ Yes |
| `LOBBYLENS_CHANNELS` | Comma-separated Slack channel IDs | ✅ Yes |

### Optional API Keys (for Daily Signals)

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `CONGRESS_API_KEY` | Congress API key for bills/hearings | ⚠️ Recommended |
| `FEDERAL_REGISTER_API_KEY` | Federal Register API key | ⚠️ Recommended |
| `REGULATIONS_GOV_API_KEY` | Regulations.gov API key | ⚠️ Recommended |

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
| `CONGRESS_API_KEY` | - | Congress API key for bills/hearings |
| `FEDERAL_REGISTER_API_KEY` | - | Federal Register API key (optional) |
| `REGULATIONS_GOV_API_KEY` | - | Regulations.gov API key |
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

## Testing Plan

### Quarterly Testing
- **Fixture Data**: Download most recent LDA quarter (Senate + House bulk files)
- **Local Processing**: Import into Postgres, run normalization, generate reports
- **Output Validation**: Review CSVs and quarterly report for accuracy
- **Slack Dry-Run**: Format mock quarterly summary (no posting)

### Daily Signals Testing
- **Live API Testing**: Use 24h window with real APIs or canned fixtures
- **Scoring Validation**: Verify priority scoring sorts items correctly
- **Watchlist Testing**: Inject known hits to test trigger logic
- **Surge Detection**: Test comment surge detection with test deltas
- **Slack Dry-Run**: Render digest blocks, ensure proper section capping

### Local Development
```bash
# Test quarterly pipeline
python -m bot.quarterly --dry-run

# Test daily signals
python -m bot.daily_signals --dry-run

# Test full integration
python -m bot.enhanced_run --mode server --dry-run
```

## Development

### Prerequisites

- Python 3.10+
- PostgreSQL (for production) or SQLite (for development)
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

LobbyLens uses a custom database schema designed for both quarterly LDA analysis and daily signals:

```sql
-- Core entities (clients, registrants)
entity(id, name, type)

-- Issue codes (HCR, TAX, DEF, etc.)
issue(id, code, description)

-- Filing records (quarterly LDA data)
filing(id, client_id, registrant_id, filing_date, created_at, amount, url, description)

-- Filing-issue relationships (many-to-many)
filing_issue(id, filing_id, issue_id)

-- Daily signal events (v2 system)
signal_event(id, source, source_id, ts, title, link, agency, committee, bill_id, rin, docket_id, issue_codes, metric_json, priority_score, created_at)

-- Channel-specific settings
channel_settings(channel_id, threshold, show_summaries, created_at)

-- Watchlist management
watchlist(channel_id, entity_type, name, display_name, entity_id, fuzzy_score, created_at)
```

## Troubleshooting

### Common Issues

**No notifications received:**
- Check Slack webhook URL is correct
- Verify webhook has proper channel permissions
- Check GitHub Actions logs for errors

**Database not found:**
- Database is created automatically on first run
- Check `DATABASE_FILE` path in configuration
- Ensure proper file permissions

**API rate limits:**
- Congress API: 5000 requests/day
- Federal Register: No rate limit (be respectful)
- Regulations.gov: 1000 requests/day
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
- Built with direct government API integrations for real-time data
