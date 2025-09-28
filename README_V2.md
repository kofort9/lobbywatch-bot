# LobbyLens v2 - Enhanced Government Signals System

## 🎯 Overview

LobbyLens v2 is a comprehensive government signals monitoring system that collects, processes, and formats daily government activity into digestible Slack digests. The system uses deterministic rules (no AI/ML) to classify, prioritize, and present government signals from multiple sources.

## 🏗️ Architecture

### Core Components

1. **SignalV2 Model** (`bot/signals_v2.py`)
   - Enhanced signal data model with priority scoring, urgency, and industry tagging
   - Supports multiple sources: Congress, Federal Register, Regulations.gov
   - Includes computed fields for classification and scoring

2. **Rules Engine** (`bot/signals_v2.py`)
   - Deterministic signal classification and urgency determination
   - Priority scoring algorithm (0-10 scale)
   - Industry mapping from issue codes
   - Watchlist matching logic

3. **Database Layer** (`bot/signals_database_v2.py`)
   - SQLite database with enhanced schema
   - Signal storage and retrieval
   - Watchlist management
   - Channel settings

4. **Digest Formatter** (`bot/digest_v2.py`)
   - Comprehensive digest formatting with industry snapshots
   - Mobile-friendly formatting with line breaks
   - Threading support for overflow content
   - Mini-digest with threshold gating

5. **Data Collector** (`bot/daily_signals_v2.py`)
   - Multi-source signal collection
   - API integration with rate limiting
   - Signal processing and storage

6. **Test Framework** (`bot/test_fixtures_v2.py`)
   - Comprehensive test fixtures
   - Validation scenarios
   - End-to-end testing

## 📊 Signal Types & Classification

### Signal Sources
- **Congress API**: Bills, hearings, markups, floor votes
- **Federal Register**: Rules, regulations, notices, hearings
- **Regulations.gov**: Dockets with comment periods and surge detection

### Signal Classification
- **Final Rule**: Federal Register final rules (priority 5.0)
- **Proposed Rule**: Federal Register proposed rules (priority 3.5)
- **Hearing**: Congressional hearings (priority 3.0)
- **Markup**: Congressional markups (priority 3.0)
- **Docket**: Regulatory dockets (priority 2.0)
- **Bill**: Congressional bills (priority 1.5)
- **Notice**: Administrative notices (priority 1.0)

### Urgency Levels
- **Critical**: Final rules effective ≤30 days
- **High**: Proposed rules with deadline ≤14 days, hearings ≤7 days, docket surges ≥200%
- **Medium**: Hearings 8-21 days, active dockets, committee referrals
- **Low**: Bill introductions, generic notices

### Industry Mapping
- **HCR** → Health
- **FIN** → Finance
- **TEC** → Tech
- **ENE** → Energy
- **ENV** → Environment
- **TRD** → Trade
- **DEF** → Defense
- **TAX** → Tax
- **TRA** → Transportation
- **EDU** → Education
- **AGR** → Agriculture
- **LAB** → Labor
- **IMM** → Immigration
- **CIV** → Civil Rights
- **COM** → Commerce
- **GOV** → Government
- **INT** → Cyber/Intel

## 🎨 Digest Format

### Daily Digest Structure
```
🔍 LobbyLens — Daily Signals (YYYY-MM-DD) · 24h
Mini-stats: Bills X · FR Y · Dockets Z · Watchlist hits W

🔎 Watchlist Alerts (max 5)
• [Industry] **Entity Name** • Urgency
  Summary • Issues: CODE • <URL|View>

📈 What Changed (max 7)
• [Industry] Signal Type — Title • Urgency
  Issues: CODE • <URL|View>

🏭 Industry Snapshots (max 12)
• [Industry] Title • Urgency
  Issues: CODE • <URL|View>

⏰ Deadlines (next 7d) (max 5)
• [Industry] Title • Deadline: Xd
  Issues: CODE • <URL|View>

📊 Docket Surges (max 3)
• [Industry] Docket Surge — Title • Urgency
  +X% / +Y (24h) • Deadline in Xd • Issues: CODE • <URL|Regulations.gov>

📜 New Bills & Actions (max 5)
• [Industry] Bill Action — Title • Urgency
  Last action: Action • Issues: CODE • <URL|Congress>

+ X more items in thread · /lobbylens help · Updated HH:MM PT
```

### Mini-Digest Format
```
⚡ Mini Signals Alert — HH:MM PT
_X signals in last 4h, Y high-priority_
• [Industry] Title • Urgency • <URL|View>
```

## 🔧 Usage

### Command Line Interface
```bash
# Run daily digest
python -m bot.run_v2 --mode daily --hours 24 --channel test_channel

# Run mini digest
python -m bot.run_v2 --mode mini --hours 4 --channel test_channel

# Run test scenarios
python -m bot.run_v2 --mode test

# Run web server
python -m bot.run_v2 --mode server --port 8000

# Dry run (no Slack posting)
python -m bot.run_v2 --mode daily --dry-run
```

### Programmatic Usage
```python
from bot.daily_signals_v2 import DailySignalsCollectorV2
from bot.digest_v2 import DigestV2Formatter
from bot.signals_database_v2 import SignalsDatabaseV2

# Initialize components
collector = DailySignalsCollectorV2(config)
formatter = DigestV2Formatter(watchlist)
database = SignalsDatabaseV2()

# Collect signals
signals = collector.collect_all_signals(hours_back=24)

# Format digest
digest = formatter.format_daily_digest(signals)

# Store in database
database.store_signals(signals)
```

## 🧪 Testing

### Test Scenarios
1. **Mixed Day**: Various signal types with different priorities
2. **Watchlist Hit**: Signals matching watchlist entities
3. **Mini Digest Threshold**: High-priority signals triggering mini-digest
4. **Character Budget Stress**: 40+ signals testing formatting limits
5. **Timezone Test**: Proper UTC/PT timezone handling

### Validation
- Digest format validation
- Section limits enforcement
- Mobile-friendly formatting
- Timezone handling
- Link formatting
- Character budget compliance

## 📈 Priority Scoring Algorithm

### Base Scores
- Final Rule: 5.0
- Floor Vote/Conference: 4.0
- Proposed Rule: 3.5
- Hearing/Markup: 3.0
- Docket: 2.0
- Bill: 1.5
- Notice: 1.0

### Modifiers
- **Urgency**: Critical +2.0, High +1.0
- **Comment Surge**: +min(2.0, log2(1 + Δ%/100))
- **Near Deadline**: +0.8 (≤3 days)
- **Watchlist Hit**: +1.5
- **Stale Update**: -1.0 (>30 days old)

### Final Score
Clamped to [0, 10] range

## 🔄 De-duplication & Grouping

### Bill Grouping
- Group by `bill_id`
- Show latest action only
- Merge multiple actions into single entry

### Docket Grouping
- Group by `docket_id`
- Show highest priority variant
- Display current total + 24h delta

### FR Document Grouping
- Group by Federal Register document number
- Remove duplicates
- Show most recent version

## 📱 Mobile-Friendly Features

### Line Breaking
- Intelligent word boundary splitting
- Proper indentation for continuation lines
- No ellipses - clean truncation

### Character Limits
- Titles: 60 characters (with line breaks)
- Summaries: 160 characters
- Section limits: 3-12 items per section

### Formatting
- Consistent emoji usage
- Clear section headers
- Proper link formatting
- Timezone display (PT)

## 🚀 Deployment

### Environment Variables
```bash
# API Keys
CONGRESS_API_KEY=your_congress_api_key
REGULATIONS_GOV_API_KEY=your_regulations_gov_api_key

# Slack Integration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your_signing_secret

# Database
DATABASE_URL=sqlite:///signals_v2.db
```

### Railway Deployment
```bash
# Deploy to Railway
railway login
railway link
railway up
```

### GitHub Actions
```yaml
# Daily digest at 8am PT
- cron: "0 15 * * *"  # 15:00 UTC = 08:00 PT

# Mini digest at 4pm PT  
- cron: "0 23 * * *"  # 23:00 UTC = 16:00 PT
```

## 📊 Performance

### Database Optimization
- Indexed columns for fast queries
- Automatic cleanup of old signals
- Efficient signal retrieval

### API Rate Limiting
- Respectful API usage
- Error handling and retries
- Graceful degradation

### Memory Management
- Efficient signal processing
- Minimal memory footprint
- Cleanup of old data

## 🔍 Monitoring

### Logging
- Structured logging with timestamps
- Error tracking and reporting
- Performance metrics

### Health Checks
- Database connectivity
- API availability
- Signal processing status

### Alerts
- High-priority signal notifications
- Watchlist hit alerts
- System health monitoring

## 🛠️ Configuration

### Channel Settings
- Mini-digest threshold (default: 10 signals)
- High-priority threshold (default: 5.0)
- Surge threshold (default: 200%)
- Show summaries toggle

### Watchlist Management
- Entity-based matching
- Fuzzy matching with confirmation
- Channel-specific watchlists
- Alias management

### Customization
- Industry mapping
- Priority weights
- Section limits
- Formatting options

## 📚 API Reference

### SignalV2 Class
```python
@dataclass
class SignalV2:
    source: str
    stable_id: str
    title: str
    summary: str
    url: str
    timestamp: datetime
    issue_codes: List[str]
    # ... additional fields
```

### SignalsRulesEngine
```python
class SignalsRulesEngine:
    def process_signal(self, signal: SignalV2) -> SignalV2
    def _classify_signal_type(self, signal: SignalV2) -> SignalType
    def _determine_urgency(self, signal: SignalV2) -> Urgency
    def _calculate_priority_score(self, signal: SignalV2) -> float
```

### DigestV2Formatter
```python
class DigestV2Formatter:
    def format_daily_digest(self, signals: List[SignalV2]) -> str
    def format_mini_digest(self, signals: List[SignalV2]) -> Optional[str]
    def _format_title_for_mobile(self, title: str, max_length: int) -> str
```

## 🎯 Future Enhancements

### Planned Features
- Quarterly LDA data integration
- Advanced watchlist matching
- Custom digest templates
- Multi-channel support
- Analytics dashboard

### Integration Opportunities
- Slack app distribution
- Webhook integrations
- API endpoints
- Mobile app support

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

For questions, issues, or feature requests, please open an issue on GitHub or contact the development team.

---

**LobbyLens v2** - Making government activity accessible and actionable through intelligent signal processing and digestible formatting.
