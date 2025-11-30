# Email Delivery Setup

Lightweight setup to test email digests locally without paid providers. Uses Python's debug SMTP server so messages are printed to stdout instead of being delivered.

## Local / Dev (free)
1) Start a local debug SMTP server (no auth, no TLS):
   ```bash
   python -m smtpd -c DebuggingServer -n localhost:1025
   ```
   Leave this running in a terminal; it will print any messages it receives.

2) Set env vars for email delivery (example `.env` snippet):
   ```bash
   NOTIFIER_TYPE=email
   SMTP_HOST=localhost
   SMTP_PORT=1025
   SMTP_USE_TLS=false
   EMAIL_FROM_ADDRESS=lobbylens@example.com
   EMAIL_TO=you@example.com
   EMAIL_SUBJECT_PREFIX=LobbyLens
   ```
   Leave `SMTP_USERNAME`/`SMTP_PASSWORD` empty for the debug server.

3) Run a digest and send via email:
   ```bash
   python -m bot.run --dry-run   # prints digest locally
   NOTIFIER_TYPE=email python -m bot.run  # sends to the debug server
   ```
   The debug SMTP terminal will show the full message payload; nothing is actually sent externally.

## Notes
- For real delivery later, swap `SMTP_HOST`/`PORT`/`TLS` and add `SMTP_USERNAME`/`SMTP_PASSWORD` for your provider (e.g., SendGrid, SES, Postmark). Keep `NOTIFIER_TYPE=email`.
- `EMAIL_TO` supports comma-separated recipients.
- If you prefer SSL on port 465, set `SMTP_PORT=465` and `SMTP_USE_TLS=false` (and use `smtplib.SMTP_SSL` in code if you extend it). Current defaults expect STARTTLS on 587.
