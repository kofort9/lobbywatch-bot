# 🚨 URGENT: Security Actions Required

**The repository is now public and credentials were exposed in git history.**

## ⚠️ IMMEDIATE ACTIONS (Do These NOW)

### 1. Rotate All Exposed Credentials

The following credentials were found in git history and need to be rotated **immediately**:

#### Database Credentials
- ✅ **PostgreSQL Database Password**: `[REDACTED - check git history or local .env]`
  - **Action**: Change the Railway PostgreSQL database password
  - **Location**: Railway dashboard → Database → Change password
  - **Update**: `DATABASE_URL` in all environments (Railway, GitHub Secrets, local `.env`)

#### Slack Credentials
- ✅ **Slack Bot Token**: `[REDACTED - xoxb-9590582352451-* - check git history]`
  - **Action**: Revoke and regenerate in Slack App settings
  - **Location**: https://api.slack.com/apps → Your App → OAuth & Permissions → Regenerate Token
  - **Update**: `SLACK_BOT_TOKEN` in GitHub Secrets, Railway, local `.env`

- ✅ **Slack Signing Secret**: `[REDACTED - 32 char hex - check git history]`
  - **Action**: Regenerate in Slack App settings
  - **Location**: https://api.slack.com/apps → Your App → Basic Information → Regenerate Signing Secret
  - **Update**: `SLACK_SIGNING_SECRET` in GitHub Secrets, Railway, local `.env`

- ✅ **Slack Webhook URL**: `[REDACTED - hooks.slack.com/services/T09***]`
  - **Action**: Delete and recreate the webhook
  - **Location**: Slack → Apps → Incoming Webhooks → Delete old, create new
  - **Update**: `SLACK_WEBHOOK_URL` in GitHub Secrets, Railway, local `.env`

#### API Keys
- ✅ **LDA API Key**: `[REDACTED - 40 char hex - check git history]`
  - **Action**: Request new API key from U.S. Senate LDA
  - **Location**: https://lda.senate.gov/api/ (contact for key rotation)
  - **Update**: `LDA_API_KEY` in GitHub Secrets, Railway, local `.env`

- ✅ **Congress API Key**: `[REDACTED - starts with 4Nfl - check git history]`
  - **Action**: Regenerate at https://api.congress.gov/sign-up/
  - **Update**: `CONGRESS_API_KEY` in GitHub Secrets, Railway, local `.env`

- ✅ **Regulations.gov API Key**: `[REDACTED - starts with SnAf - check git history]`
  - **Action**: Regenerate at https://open.gsa.gov/api/regulationsgov/
  - **Update**: `REGULATIONS_GOV_API_KEY` in GitHub Secrets, Railway, local `.env`

### 2. Update All Deployment Environments

After rotating credentials, update them in:

- [ ] **GitHub Repository Secrets** (Settings → Secrets and variables → Actions)
  - `DATABASE_URL`
  - `SLACK_BOT_TOKEN`
  - `SLACK_SIGNING_SECRET`
  - `SLACK_WEBHOOK_URL`
  - `LDA_API_KEY`
  - `CONGRESS_API_KEY`
  - `REGULATIONS_GOV_API_KEY`

- [ ] **Railway Environment Variables**
  - All of the above variables

- [ ] **Local `.env` file**
  - Update with new credentials

### 3. Verify .env is NOT Tracked

Check that `.env` is not in git:
```bash
git ls-files .env
```

If it shows `.env`, remove it immediately:
```bash
git rm --cached .env
git commit -m "Remove .env from tracking"
```

## 🔄 Optional: Clean Git History

**Warning**: This rewrites git history and requires force push. Only do this if:
- You have coordination with your team
- You're okay with rewriting history
- All collaborators are aware

### Option 1: Using git-filter-repo (Recommended)

```bash
# Install git-filter-repo if needed
pip install git-filter-repo

# Remove sensitive data from history
# Extract actual credentials from your local .env or git history first
git filter-repo --replace-text <(echo "YOUR_POSTGRES_PASSWORD==>REDACTED")
git filter-repo --replace-text <(echo "YOUR_SLACK_BOT_TOKEN==>REDACTED")
git filter-repo --replace-text <(echo "YOUR_SLACK_SIGNING_SECRET==>REDACTED")
git filter-repo --replace-text <(echo "YOUR_LDA_API_KEY==>REDACTED")
git filter-repo --replace-text <(echo "YOUR_CONGRESS_API_KEY==>REDACTED")
git filter-repo --replace-text <(echo "YOUR_REGS_GOV_API_KEY==>REDACTED")

# Force push (WARNING: This rewrites history)
git push origin --force --all
git push origin --force --tags
```

### Option 2: Using BFG Repo-Cleaner

```bash
# Download BFG
# https://rtyley.github.io/bfg-repo-cleaner/

# Create passwords file
echo "SGPGDpHWGQkoikWPSlkVSvaRHxFrXsWl" > passwords.txt
echo "xoxb-9590582352451-9580667884167-CdQTL0etRC5gFUmjoEmZDGbv" >> passwords.txt
echo "ccf7df297a7a8b10c9ce66960fa02060" >> passwords.txt
echo "37cdd62e714fd57d6cad079da319c85cc1880e9d" >> passwords.txt
echo "4NflKAVXBXUQA5IDbX70MPFvGPEVgp4UZebmo4s8" >> passwords.txt
echo "SnAfj6ilRbuXer9801MSxHysG0LVSvGdCnYeGzHT" >> passwords.txt

# Clean repository
java -jar bfg.jar --replace-text passwords.txt

# Force push
git push origin --force --all
```

### Option 3: Accept the Exposure (Not Recommended)

If you cannot coordinate history rewrite, accept that:
- Credentials are exposed in git history
- Anyone can clone the repo and see them
- **MUST rotate all credentials immediately** (this is non-negotiable)

## 📋 Checklist

- [ ] Rotate PostgreSQL database password
- [ ] Regenerate Slack bot token
- [ ] Regenerate Slack signing secret
- [ ] Delete and recreate Slack webhook
- [ ] Request new LDA API key
- [ ] Regenerate Congress API key
- [ ] Regenerate Regulations.gov API key
- [ ] Update GitHub Secrets
- [ ] Update Railway environment variables
- [ ] Update local `.env` file
- [ ] Test all integrations with new credentials
- [ ] (Optional) Clean git history if coordinated with team
- [ ] Document the incident and resolution

## 🎯 Priority Order

1. **Rotate credentials** (highest priority - do this first)
2. **Update deployment environments** (so services continue working)
3. **Test integrations** (verify everything still works)
4. **Clean git history** (optional, can be done later if needed)

## ⏱️ Timeline

- **Immediate (Next 30 minutes)**: Rotate all credentials
- **Within 1 hour**: Update all deployment environments
- **Within 2 hours**: Test and verify all integrations work
- **Within 24 hours**: Decide on git history cleanup approach

## 📞 Support

If you need help:
- Check service-specific documentation for credential rotation
- Contact support for services if rotation is not self-service
- Coordinate with team members if cleaning git history

---

**Remember**: The most important thing is to rotate the credentials immediately. Git history cleanup can wait, but credential rotation cannot.

