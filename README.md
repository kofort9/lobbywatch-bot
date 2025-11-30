# LobbyLens

**LobbyLens** is a comprehensive government monitoring and analysis platform that provides real-time tracking of government activity and quarterly lobbying disclosure analysis. The system integrates multiple government data sources to deliver actionable intelligence through Slack and email notifications.

> **Note**: The production deployment is currently offline due to Railway credit limitations. The codebase is fully functional and can be deployed to any compatible hosting platform. Local development and testing remain fully supported.

## Overview

LobbyLens operates on a two-layer architecture:

- **V2: Daily Activity Monitoring** — Real-time tracking of government actions including bills, hearings, regulations, and regulatory actions
- **V1: Quarterly Lobbying Analysis** — Comprehensive analysis of lobbying disclosure data from the U.S. Senate LDA system

## Architecture

### V2: Daily Activity Layer (Active)

The daily activity layer monitors government operations in real-time through official APIs:

- **Data Sources**: Congress API, Federal Register API, Regulations.gov API
- **Content**: Bills, hearings, regulations, regulatory actions, comment periods
- **Deployment**: Railway-hosted service with Docker support
- **Features**:
  - Priority-based signal scoring and filtering
  - Watchlist-based alerting
  - Industry categorization and snapshots
  - Mobile-optimized digest formatting
  - Automated daily and mini-digest generation

### V1: Quarterly Lobbying Analysis (Production Ready)

The quarterly analysis layer processes lobbying disclosure data:

- **Data Source**: U.S. Senate LDA REST API
- **Purpose**: Track lobbying expenditures, registrants, clients, and issue codes
- **Database**: PostgreSQL (Railway-managed) for production scalability
- **Status**: Production-ready with comprehensive ETL pipeline
- **Features**:
  - Front-page digest focusing on high-impact filings
  - Top registrants, clients, and issue analysis
  - Quarter-over-quarter trend tracking
  - Amendment detection and tracking
  - Admin-controlled digest posting

## Features

### Daily Government Activity Monitoring

- **Intelligent Signal Processing**: Rule-based priority scoring with configurable weights
- **Watchlist Alerts**: Real-time notifications for entities matching configured watchlists
- **Industry Categorization**: Automatic mapping of agencies and committees to industry sectors
- **Deadline Tracking**: Identification of upcoming comment periods and effective dates
- **Surge Detection**: Recognition of significant increases in regulatory comment activity
- **Mobile-Optimized Formatting**: Character budgets and line breaking for mobile readability

### Lobbying Disclosure Analysis

- **Front-Page Digest**: Curated analysis of high-impact lobbying activity
- **Trend Analysis**: Quarter-over-quarter comparisons and movement tracking
- **Entity Search**: Fuzzy matching for registrants, clients, and entities
- **Issue Code Mapping**: Automatic categorization using official LDA issue codes
- **Data Export**: CSV and structured data exports for further analysis

### Platform Capabilities

- **Multi-Channel Delivery**: Slack integration with slash commands and email notifications
- **Automated Scheduling**: GitHub Actions workflows for daily, weekly, and quarterly updates
- **Secure Configuration**: Environment-based secrets management with signature verification
- **Comprehensive Testing**: 63% test coverage with deterministic, rule-based logic
- **Interactive Commands**: Full Slack slash command interface for on-demand access

## Data Sources

### Daily Activity Sources

| Source | Content | Refresh Frequency |
|--------|---------|------------------|
| Congress API | Bills, votes, hearings, committee actions | Daily (8 AM PT) |
| Federal Register API | Rules, notices, regulatory actions | Daily (8 AM PT) |
| Regulations.gov API | Dockets, comment counts, regulatory surges | Daily (8 AM PT) + Mini (4 PM PT) |

### Quarterly Lobbying Data

| Source | Content | Refresh Frequency |
|--------|---------|-------------------|
| U.S. Senate LDA API | Lobbying filings, registrants, clients, amounts | Quarterly (when published) |

## Slack Integration

LobbyLens provides comprehensive Slack integration with interactive slash commands for digest generation, watchlist management, and system configuration.

**Security & handlers**
- All Slack HTTP entrypoints enforce signing secret verification; production fails closed if `SLACK_SIGNING_SECRET` is missing.
- Flask routes now reuse the richer `bot.slack_app.SlackApp` handler stack (admin checks, confirmations, watchlist flows) so behaviour stays consistent across slash commands and events.
- A `use_legacy_handlers` flag exists for tests/local fallback; keep it disabled in production.

### Digest Commands

- `/lobbypulse` — Generate daily digest (24-hour window)
- `/lobbypulse mini` — Generate mini digest (4-hour window, threshold-based)
- `/lobbypulse help` — Display command reference

### Watchlist Management

- `/watchlist add <entity>` — Add entity to watchlist
- `/watchlist remove <entity>` — Remove entity from watchlist
- `/watchlist list` — Display current watchlist

### Configuration

- `/threshold set <number>` — Configure mini-digest threshold
- `/threshold` — Display current threshold settings

### LDA Commands (Admin Only)

- `/lobbylens lda digest [q=2024Q3]` — Post LDA quarterly digest
- `/lobbylens lda top registrants [q=2024Q3] [n=10]` — Display top lobbying firms
- `/lobbylens lda top clients [q=2024Q3] [n=10]` — Display top lobbying clients
- `/lobbylens lda issues [q=2024Q3]` — Display top lobbying issues
- `/lobbylens lda entity <name>` — Search for specific entity
- `/lobbylens lda help` — Display LDA system help

### System Commands

- `/lobbylens` — Display system status and statistics
- `/lobbylens help` — Display comprehensive system help

## Quick Start

### Prerequisites

- Python 3.10 or higher
- PostgreSQL (production) or SQLite (development)
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/lobbylens.git
cd lobbylens

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Configuration

1. **Environment Setup**

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
# Required: Slack credentials, API keys, database URL
```

2. **Slack App Configuration**

   - Create a Slack app at https://api.slack.com/apps
   - Configure OAuth & Permissions with required scopes
   - Add an Incoming Webhook to your desired channel
   - Copy webhook URL, bot token, and signing secret to `.env`

3. **API Keys**

   - **Congress API**: Register at https://api.congress.gov/sign-up/
   - **Regulations.gov API**: Register at https://open.gsa.gov/api/regulationsgov/
   - **LDA API**: Contact U.S. Senate LDA for API access

### Running Locally

```bash
# Test with dry run (no notifications)
lobbylens --dry-run

# Run normally (sends notifications)
lobbylens

# Skip data fetching (use existing database)
lobbylens --skip-fetch
```

## Deployment

### Current Status

**Production Deployment**: Currently offline due to Railway credit limitations. The application can be deployed to any compatible hosting platform that supports PostgreSQL and Python 3.10+.

### Railway Deployment

LobbyLens is configured for deployment on Railway with PostgreSQL (when credits are available):

1. **Database Setup**: Railway automatically provisions PostgreSQL
2. **Environment Variables**: Configure all required secrets in Railway dashboard
3. **Deployment**: Push to main branch triggers automatic deployment

**Alternative Deployment Options**:
- **Heroku**: Compatible with PostgreSQL add-on
- **Render**: Supports PostgreSQL and Python applications
- **DigitalOcean App Platform**: PostgreSQL and Python runtime support
- **AWS/GCP/Azure**: Full control with managed PostgreSQL services
- **Self-hosted**: Deploy on any server with PostgreSQL and Docker support

### GitHub Actions

Automated workflows handle scheduled operations:

- **Daily Digest** (`.github/workflows/daily.yml`): Runs at 8:00 AM PT daily
- **Weekly Collector** (`.github/workflows/weekly-collector.yml`): Runs Fridays at 23:00 UTC
- **Quarterly LDA Update** (`.github/workflows/lda-quarterly.yml`): Runs monthly on the 15th
- **Testing** (`.github/workflows/test.yml`): Runs on every push and pull request

### Required Secrets

Configure these secrets in GitHub repository settings:

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `SLACK_BOT_TOKEN` | Slack bot token for enhanced features | Yes |
| `SLACK_SIGNING_SECRET` | Slack signing secret for request verification | Yes |
| `LOBBYLENS_CHANNELS` | Comma-separated Slack channel IDs | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes (production) |
| `CONGRESS_API_KEY` | Congress API key | Recommended |
| `REGULATIONS_GOV_API_KEY` | Regulations.gov API key | Recommended |
| `LDA_API_KEY` | U.S. Senate LDA API key | Optional (V1 features) |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | - | PostgreSQL connection string (production) |
| `DATABASE_FILE` | `lobbywatch.db` | SQLite database path (development) |
| `SLACK_WEBHOOK_URL` | - | Slack webhook URL (legacy) |
| `SLACK_BOT_TOKEN` | - | Slack bot token for enhanced features |
| `SLACK_SIGNING_SECRET` | - | Slack signing secret for request verification |
| `LOBBYLENS_ADMIN_USER_ID` | - | Slack user ID for DM alerts |
| `ENABLE_LDA_V1` | `false` | Enable LDA V1 features |
| `LDA_API_KEY` | - | U.S. Senate LDA API key |
| `CONGRESS_API_KEY` | - | Congress API key |
| `REGULATIONS_GOV_API_KEY` | - | Regulations.gov API key |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARN, ERROR) |
| `DRY_RUN` | `false` | Generate digest without sending |
| `ENVIRONMENT` | `development` | Environment (development, staging, production) |

### Database Configuration

**PostgreSQL (Production - Recommended)**

```bash
DATABASE_URL=postgresql://user:password@host:port/database
```

**SQLite (Development - Fallback)**

```bash
DATABASE_FILE=lobbywatch.db
```

The system automatically detects PostgreSQL when `DATABASE_URL` is set and falls back to SQLite otherwise.

## Development

### Project Structure

```
lobbylens/
├── bot/                    # Main application package
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── digest.py          # Daily digest computation
│   ├── daily_signals.py   # Signal collection and processing
│   ├── signals_database.py # Signal persistence layer
│   ├── run.py             # CLI entry point
│   ├── web_server.py      # Flask web server for Slack
│   ├── api.py             # FastAPI endpoints
│   ├── notifiers/         # Notification providers
│   │   ├── base.py        # Base notification protocol
│   │   ├── slack.py       # Slack implementation
│   │   └── email.py       # Email implementation
│   └── ...
├── govsearch/             # Search service (FastAPI + Streamlit)
├── tests/                 # Test suite
│   ├── conftest.py       # Pytest fixtures
│   └── test_*.py         # Test modules
├── scripts/              # Utility scripts
├── docs/                 # Documentation
├── .github/workflows/    # GitHub Actions
├── pyproject.toml        # Project configuration
└── README.md            # This file
```

### Testing

The test suite includes comprehensive coverage:

- **Unit Tests**: Module-level testing with 63% overall coverage
- **Integration Tests**: End-to-end workflow validation
- **API Tests**: External API integration testing with mocks
- **Security Tests**: Signature verification and permission checks

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=bot --cov-report=html

# Run specific test suite
pytest tests/test_digest.py -v
pytest tests/test_api.py -v
```

### Code Quality

```bash
# Format code
black bot tests
isort bot tests

# Type checking
mypy bot

# Linting
flake8 bot tests
```

### Developer Utilities

**Preview Local Digest**

```bash
# Render digest from local SQLite cache
python scripts/maintenance/preview_local_digest.py --db signals.db --hours 24

# Render digest from Railway PostgreSQL
python scripts/maintenance/preview_local_digest.py --db "$DATABASE_URL" --hours 48
```

**Sync Signals from PostgreSQL**

```bash
python scripts/maintenance/sync_signals_from_postgres.py \
  --postgres "$DATABASE_URL" \
  --sqlite signals.db \
  --hours 72
```

## Security

LobbyLens implements multiple security measures:

- **Request Verification**: All Slack endpoints verify request signatures using HMAC-SHA256
- **Fail-Closed Permissions**: Permission checks deny access by default on errors
- **Environment-Based Secrets**: All credentials managed through environment variables
- **Production Hardening**: Signature verification required in production environments

See `docs/SECURITY.md` for current security posture, required actions, and testing notes. `docs/SECURITY_CLEANUP.md` documents historical exposure and git-rewrite options.

## Database Schema

The system uses a hybrid schema supporting both daily signals and quarterly lobbying data:

```sql
-- Core entities
entity(id, name, type)

-- Issue codes
issue(id, code, description)

-- Filing records (quarterly LDA data)
filing(id, client_id, registrant_id, filing_date, created_at, amount, url, description)

-- Filing-issue relationships
filing_issue(id, filing_id, issue_id)

-- Daily signal events
signal_event(id, source, source_id, timestamp, title, link, agency, committee, 
             bill_id, rin, docket_id, issue_codes, metrics_json, priority_score, created_at)

-- Channel-specific settings
channel_settings(channel_id, threshold, show_summaries, created_at)

-- Watchlist management
watchlist(channel_id, entity_type, name, display_name, entity_id, fuzzy_score, created_at)
```

## Troubleshooting

### Common Issues

**No notifications received**
- Verify Slack webhook URL and bot token are correct
- Check webhook has proper channel permissions
- Review GitHub Actions logs for errors
- Ensure `SLACK_SIGNING_SECRET` is configured for production

**Database connection errors**
- Verify `DATABASE_URL` format (PostgreSQL) or `DATABASE_FILE` path (SQLite)
- Check database permissions and network connectivity
- Ensure database schema is initialized

**API rate limits**
- Congress API: 5,000 requests/day
- Federal Register: No official limit (use responsibly)
- Regulations.gov: 1,000 requests/day
- Consider adjusting fetch limits in configuration

**Signature verification failures**
- Ensure `SLACK_SIGNING_SECRET` matches Slack app configuration
- Verify request timestamp is within 5-minute window
- Check that raw request body is used for signature calculation

### Debug Mode

```bash
# Enable verbose logging
export LOG_LEVEL=DEBUG
lobbylens --dry-run

# Test Slack notification
python -c "from bot.notifiers.slack import SlackNotifier; \
           SlackNotifier('YOUR_WEBHOOK').send('Test message')"
```

## Documentation

Additional documentation is available in the `docs/` directory:

- `LDA_OVERVIEW.md` — LDA V1 implementation details
- `OPERATIONS_GUIDE.md` — Deployment and operations reference
- `TEST_COVERAGE.md` — Test coverage metrics and targets
- `TECHNICAL_DEBT.md` — Known issues and improvement areas
- `IMPROVEMENTS.md` — Planned enhancements
- `docs/SECURITY.md` — Security posture, required actions, and testing
- `docs/SECURITY_CLEANUP.md` — History of exposure and git cleanup guidance

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and add tests
4. Run the full test suite: `pytest`
5. Ensure code quality: `black . && isort . && flake8 .`
6. Submit a pull request with a clear description

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [U.S. Senate LDA API](https://lda.senate.gov/api/) for lobbying disclosure data
- [Congress API](https://api.congress.gov/) for legislative data
- [Federal Register API](https://www.federalregister.gov/api/v1) for regulatory data
- [Regulations.gov API](https://open.gsa.gov/api/regulationsgov/) for docket information

Built with direct government API integrations for real-time, authoritative data.
