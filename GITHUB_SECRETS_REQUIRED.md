# 🔐 GitHub Secrets Configuration for LobbyLens

This document lists all GitHub repository secrets required for automated daily V2 digests and quarterly LDA V1 digests.

## 📋 **Required Secrets**

### **Core Slack Integration**
| Secret Name | Description | Required For | Example Value |
|-------------|-------------|--------------|---------------|
| `SLACK_BOT_TOKEN` | Slack bot token for posting messages | V2 Daily + LDA V1 | `xoxb-9590582352451-9580667884167-...` |
| `SLACK_SIGNING_SECRET` | Slack signing secret for request verification | V2 Daily + LDA V1 | `ccf7df297a7a8b10c9ce66960fa02060` |
| `SLACK_WEBHOOK_URL` | Slack webhook URL for posting digests | V2 Daily | `https://hooks.slack.com/services/...` |
| `LOBBYLENS_CHANNELS` | Comma-separated channel IDs to post to | V2 Daily + LDA V1 | `C123456,C789012` |

### **V2 Daily Digest APIs**
| Secret Name | Description | Required For | How to Get |
|-------------|-------------|--------------|------------|
| `CONGRESS_API_KEY` | Congress.gov API key | V2 Daily | https://api.congress.gov/sign-up/ |
| `REGULATIONS_GOV_API_KEY` | Regulations.gov API key | V2 Daily | https://open.gsa.gov/api/regulationsgov/ |

**Note:** Federal Register API doesn't require an API key (free service), so no secret needed.

### **LDA V1 Quarterly System**
| Secret Name | Description | Required For | Example Value |
|-------------|-------------|--------------|---------------|
| `DATABASE_URL` | PostgreSQL connection string | LDA V1 | `postgresql://postgres:...@switchback.proxy.rlwy.net:37990/railway` |
| `LDA_API_KEY` | U.S. Senate LDA API key | LDA V1 | `37cdd62e714fd57d6cad079da319c85cc1880e9d` |
| `LOBBYLENS_ADMIN_USER_ID` | Admin user ID for DM alerts | LDA V1 | `U09HCH4AQ1H` |

### **Legacy V1 System (Removed)**
| Secret Name | Description | Status |
|-------------|-------------|--------|
| ~~`OPENSECRETS_API_KEY`~~ | OpenSecrets API key | ❌ Removed (not needed) |
| ~~`PROPUBLICA_API_KEY`~~ | ProPublica API key | ❌ Removed (not needed) |
| ~~`FEDERAL_REGISTER_API_KEY`~~ | Federal Register API key | ❌ Removed (free service) |

## 🕐 **Scheduling Configuration**

### **Daily V2 Digest**
- **Schedule**: Every day at 15:00 UTC (8:00 AM PT)
- **Workflow**: `.github/workflows/daily.yml`
- **What it does**: 
  - Collects government activity from Congress, Federal Register, Regulations.gov
  - Generates industry snapshots and priority-scored digest
  - Posts to Slack channels via webhook

### **Quarterly LDA V1 Digest**
- **Schedule**: 15th of each month at 08:00 UTC (quarterly filings due 45 days after quarter end)
- **Workflow**: `.github/workflows/lda-quarterly.yml`
- **What it does**:
  - Runs ETL to fetch latest LDA filings from Senate API
  - Updates PostgreSQL database with new lobbying data
  - Generates "front page" digest with biggest hitters
  - Posts to Slack channels via bot token

## 🚀 **Setup Instructions**

### **1. Add Secrets to GitHub Repository**

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

Add each secret from the tables above with the exact name and your actual values.

### **2. Get Slack Channel IDs**

Use the provided script to get channel IDs:
```bash
python scripts/get-slack-user-id.py
```

Set `LOBBYLENS_CHANNELS` to comma-separated channel IDs like: `C123456789,C987654321`

### **3. Test Manual Triggers**

Both workflows support manual triggering:

**Daily Digest (V2):**
- Go to Actions → LobbyLens Daily Digest → Run workflow
- Should post V2 digest immediately

**Quarterly LDA (V1):**
- Go to Actions → LDA Quarterly Update → Run workflow
- Choose "update" mode for current data
- Should run ETL and post LDA digest

### **4. Verify Scheduling**

After setup, you should receive:
- **Daily at 8:00 AM PT**: V2 government activity digest
- **Monthly on 15th**: LDA quarterly money digest (when new data available)

## 🔧 **Current Configuration Status**

Based on your `.env` file, you already have:
- ✅ `SLACK_BOT_TOKEN` - configured
- ✅ `SLACK_SIGNING_SECRET` - configured  
- ✅ `DATABASE_URL` - Railway PostgreSQL configured
- ✅ `LDA_API_KEY` - configured
- ✅ `LOBBYLENS_ADMIN_USER_ID` - configured

**GitHub Secrets Status:**
- ✅ `CONGRESS_API_KEY` - added
- ✅ `REGULATIONS_GOV_API_KEY` - added
- ✅ `SLACK_WEBHOOK_URL` - added
- ✅ `LOBBYLENS_CHANNELS` - added

**Ready for testing!** 🚀

## 📞 **Support**

If you encounter issues:
1. Check GitHub Actions logs for specific error messages
2. Verify all secrets are set correctly (no typos in names)
3. Test manual workflow triggers first
4. Check Slack permissions for bot token

## 🎯 **Expected Behavior**

**Starting tomorrow (Monday):**
- You should receive a V2 daily digest at 8:00 AM PT
- This will continue daily with government activity updates

**Next quarterly cycle:**
- LDA V1 digest will post when new quarterly data is available
- Typically within 45 days after quarter end (15th of month following quarter)

The system is now configured to automatically deliver both daily government activity updates and quarterly lobbying money insights!
