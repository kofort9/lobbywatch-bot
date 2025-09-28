# 🔍 LobbyLens Enhanced Features

LobbyLens now supports advanced interactive features including watchlists, smart digests, and slash commands. This document covers the enhanced functionality.

## 🚀 Quick Start

### 1. Basic vs Enhanced Mode

**Basic Mode** (webhook only):
- Daily digests via webhook
- No interactivity 
- Set `SLACK_WEBHOOK_URL`

**Enhanced Mode** (full Slack app):
- Interactive slash commands
- Channel-specific watchlists
- Dual cadence digests (8am + 4pm)
- Threshold-based alerts
- Rich formatting with context

### 2. Slack App Setup

1. **Create Slack App**:
   - Go to https://api.slack.com/apps
   - "Create New App" → "From scratch"
   - Choose app name (e.g., "LobbyLens") and workspace

2. **Configure Bot Token**:
   - Go to "OAuth & Permissions"
   - Add scopes: `chat:write`, `commands`, `channels:read`
   - Install app to workspace
   - Copy "Bot User OAuth Token"

3. **Set Up Slash Commands**:
   - Go to "Slash Commands"
   - Create these commands pointing to `https://yourdomain.com/slack/commands`:
     - `/watchlist` - Manage watchlist
     - `/threshold` - Set alert thresholds  
     - `/summary` - Toggle descriptions
     - `/lobbylens` - Manual actions

4. **Enable Events**:
   - Go to "Event Subscriptions"
   - Set Request URL: `https://yourdomain.com/slack/events`
   - Subscribe to: `message.channels`

5. **Get Signing Secret**:
   - Go to "Basic Information" 
   - Copy "Signing Secret"

### 3. Environment Configuration

```bash
# Required for enhanced features
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret

# Channels for automated digests (comma-separated IDs)
LOBBYLENS_CHANNELS=C1234567890,C0987654321

# API keys for daily signals
CONGRESS_API_KEY=your-key
FEDERAL_REGISTER_API_KEY=your-key
REGULATIONS_GOV_API_KEY=your-key
```

## 📊 Enhanced Digests

### Format Improvements

**Before:**
```
New filings (last 24h):
• Apple Inc → Akin Gump ($50K)
```

**After:**
```
🔍 LobbyLens Daily Digest — 2024-10-15 • 🎯 2 watchlist matches

📋 New filings (last 24h):
• **Apple Inc** → Akin Gump Strauss ($50K) - AI regulation advocacy • <link|View>
• Microsoft Corp → Brownstein Hyatt ($75K) - Cloud infrastructure policy
```

### New Features

- **Watchlist highlighting**: Bold text for matches
- **Descriptions**: Short filing summaries
- **Direct links**: Click to view official filings
- **Context**: Example clients and issues for top registrants
- **Match counts**: Shows watchlist hits in header

### Dual Cadence

1. **Daily Digest** (8:00 AM PT):
   - Full summary of last 24h
   - Top registrants with context
   - Issue activity trends

2. **Mini Digest** (4:00 PM PT):
   - Sent only if thresholds met:
     - ≥10 new filings since morning, OR
     - Any watchlist entity appears
   - Focused on new activity since morning
   - Shorter format

## 🎯 Watchlists

### Channel-Specific Watchlists

Each Slack channel has its own independent watchlist for:
- **Clients**: Companies hiring lobbyists
- **Registrants**: Lobbying firms  
- **Issues**: Policy areas (HCR, TAX, etc.)

### Adding Entities

```bash
/watchlist add Google
```

**Smart Matching Process:**

1. **Exact Match** → Auto-added
2. **High Confidence** (95%+) → Auto-added  
3. **Medium Confidence** (85-94%) → Confirmation prompt
4. **Low Confidence** (<85%) → Shows alternatives

**Example Confirmation:**
```
Possible matches for 'Google':
1) Alphabet Inc. (Google) (92% match)
2) Google Fiber Inc. (89% match) 
3) Google Cloud LLC (87% match)

Reply with number (1-3), 'all', or 'q' to cancel.
```

### Alias Learning

LobbyLens learns from your confirmations:
- "Google" → "Alphabet Inc." gets saved
- Next time "Google" is instant match
- Improves over time across all channels

## 💻 Slash Commands

### `/watchlist` - Manage Watchlist

```bash
/watchlist list                    # Show current watchlist
/watchlist add Apple              # Add entity with fuzzy matching  
/watchlist add "tax policy"       # Add issue/topic (use quotes for multi-word)
/watchlist remove "Apple Inc"     # Remove entity
```

### `/threshold` - Set Alert Thresholds

```bash
/threshold                        # Show current thresholds
/threshold set filings 15         # Mini-digest needs 15+ filings
/threshold set amount 250000      # Alert for $250K+ individual filings
```

### `/summary` - Toggle Descriptions

```bash
/summary                          # Show current setting
/summary on                       # Show filing descriptions in digests
/summary off                      # Hide descriptions (more compact)
```

### `/lobbylens` - Manual Actions

```bash
/lobbylens digest                 # Generate manual digest now
/lobbylens                        # Show help
```

## 🚨 Smart Alerts

### Watchlist Highlights

Watchlist matches appear **bold** in digests:
```
📋 New filings:
• **Apple Inc** → Covington & Burling ($180K)  [watchlist hit]
• Samsung Corp → Gibson Dunn ($95K)
```

### Mini-Digest Triggers

Sent at 4:00 PM PT if:
- ≥ threshold filings since morning digest, OR
- Any watchlist entity has new activity

### Threshold Alerts

For major filings exceeding amount threshold:
```
🚨 LobbyLens Alert

High-value filing detected:
Apple Inc → Akin Gump ($500K) on Technology Policy

<link|View Filing>
```

## 🔧 Deployment

### Web Server Mode

Enhanced features require a web server to handle Slack events:

```bash
# Start web server
lobbylens-enhanced --mode server --port 3000

# Docker deployment
docker build -t lobbylens .
docker run -p 3000:3000 -e SLACK_BOT_TOKEN=$TOKEN lobbylens

# Kubernetes/Railway/Heroku supported
```

### GitHub Actions Updates

Enhanced mode supports both scheduled and server deployments:

**Option 1: Scheduled Only** (daily digest)
```yaml
- name: Run daily digest
  run: lobbylens-enhanced --mode daily
```

**Option 2: Web Server** (full interactivity)
```yaml
- name: Deploy to Railway/Heroku
  # Deploy web server with webhooks
```

### Environment Variables

```bash
# Core database
DATABASE_FILE=lobbywatch.db

# Daily signals API keys
CONGRESS_API_KEY=key
FEDERAL_REGISTER_API_KEY=key
REGULATIONS_GOV_API_KEY=key

# Enhanced Features
SLACK_BOT_TOKEN=xoxb-token           # Required for enhanced mode
SLACK_SIGNING_SECRET=secret          # Required for enhanced mode  
LOBBYLENS_CHANNELS=C123,C456         # Auto-digest channels
SLACK_WEBHOOK_URL=webhook            # Fallback/legacy support

# Web Server
PORT=3000                            # Server port (default: 3000)
```

## 📋 Database Schema

Enhanced features add these tables:

```sql
-- Channel settings (thresholds, preferences)
channel_settings(id, threshold_filings, threshold_amount, show_descriptions)

-- Per-channel watchlists  
channel_watchlist(channel_id, entity_type, watch_name, display_name, fuzzy_score)

-- Learned aliases for fast matching
entity_aliases(alias_name, canonical_name, entity_type, confidence_score)

-- Digest run tracking
digest_runs(channel_id, run_type, run_time, filings_count)

-- Filing processing state
filing_tracking(filing_id, processed_at, digest_sent_to, watchlist_matches)
```

All backward compatible with existing databases.

## 🧪 Testing Enhanced Features

### 1. Test Fuzzy Matching

```bash
# Terminal test
python -c "
from bot.database import DatabaseManager
from bot.matching import MatchingService

db = DatabaseManager('test.db')
db.ensure_enhanced_schema()
service = MatchingService(db)

result = service.process_watchlist_add('C123', 'google')
print(result)
"
```

### 2. Test Enhanced Digest

```bash
# Generate test digest
SLACK_BOT_TOKEN=test SLACK_SIGNING_SECRET=test LOBBYLENS_CHANNELS=C123 \
lobbylens-enhanced --mode daily --channel C123 --dry-run
```

### 3. Test Slash Commands

```bash
# Start test server
lobbylens-enhanced --mode server --port 3000

# Test with curl
curl -X POST localhost:3000/slack/commands \
  -d "command=/watchlist&text=add google&channel_id=C123&user_id=U123"
```

## 🔍 Monitoring & Debugging

### Logs

Enhanced mode provides detailed logging:

```bash
# Debug mode  
LOG_LEVEL=DEBUG lobbylens-enhanced --mode server

# Key log events
INFO: Fuzzy match: 'google' -> 'Alphabet Inc.' (95% confidence)
INFO: Watchlist hit: Apple Inc in filing #12345
INFO: Mini-digest threshold met: 12 filings > 10
```

### Health Checks

Web server includes health endpoint:

```bash
curl http://localhost:3000/health
# {"status": "healthy", "service": "lobbylens"}
```

### Database Queries

Monitor watchlist usage:
```sql  
SELECT channel_id, COUNT(*) as watchlist_size
FROM channel_watchlist 
GROUP BY channel_id;

SELECT alias_name, usage_count  
FROM entity_aliases
ORDER BY usage_count DESC LIMIT 10;
```

## 🚀 Migration from Basic to Enhanced

### Gradual Migration

1. **Keep existing webhook** (no disruption)
2. **Add enhanced environment variables**
3. **Deploy web server** alongside webhook
4. **Test in one channel** 
5. **Migrate channels one by one**

### Migration Script

```bash
# 1. Update environment
cp .env.example .env.enhanced
# Edit .env.enhanced with bot token & channels

# 2. Install enhanced version
pip install -e .

# 3. Initialize enhanced schema (preserves existing data)
python -c "
from bot.database import DatabaseManager
db = DatabaseManager('lobbywatch.db') 
db.ensure_enhanced_schema()
print('✅ Enhanced schema ready')
"

# 4. Test enhanced digest
source .env.enhanced
lobbylens-enhanced --mode daily --dry-run

# 5. Deploy web server
lobbylens-enhanced --mode server
```

The enhanced features are fully backward compatible - you can run both basic and enhanced modes simultaneously during migration.

## 📚 API Reference

### MatchingService

```python
from bot.matching import MatchingService

service = MatchingService(db_manager)

# Fuzzy match entity
result = service.process_watchlist_add(channel_id, search_term)
# Returns: {'status': 'success'|'confirmation_needed'|'no_match', ...}

# Handle confirmation
result = service.process_confirmation_response(
    channel_id, search_term, candidates, user_response
)
```

### EnhancedDigestComputer

```python  
from bot.enhanced_digest import EnhancedDigestComputer

computer = EnhancedDigestComputer(db_manager)

# Generate digest
digest = computer.compute_enhanced_digest(channel_id, 'daily')

# Check mini-digest threshold
should_send = computer.should_send_mini_digest(channel_id)
```

### SlackApp

```python
from bot.slack_app import SlackApp

app = SlackApp(db_manager)

# Handle slash command
response = app.handle_slash_command(command_data)

# Send digest
success = app.send_digest(channel_id, 'daily')
```

---

Ready to upgrade your lobbying intelligence? Enhanced LobbyLens turns your Slack into a personalized DC news room! 🎯
