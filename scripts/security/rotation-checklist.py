#!/usr/bin/env python3
"""
Credential Rotation Checklist

This script helps track which credentials have been rotated.
Run it after rotating each credential to mark it as complete.
"""

import json
import os
from pathlib import Path
from typing import Dict

CHECKLIST_FILE = Path(__file__).parent / "rotation-status.json"

CREDENTIALS = {
    "database_password": {
        "name": "PostgreSQL Database Password",
        "old_value": "[REDACTED - check git history]",
        "rotation_instructions": "Railway dashboard → Database → Change password",
        "update_locations": ["Railway DATABASE_URL", "GitHub Secrets", "local .env"],
        "rotated": False,
    },
    "slack_bot_token": {
        "name": "Slack Bot Token",
        "old_value": "[REDACTED - check git history]",
        "rotation_instructions": "https://api.slack.com/apps → Your App → OAuth & Permissions → Regenerate",
        "update_locations": ["GitHub Secrets SLACK_BOT_TOKEN", "Railway", "local .env"],
        "rotated": False,
    },
    "slack_signing_secret": {
        "name": "Slack Signing Secret",
        "old_value": "[REDACTED - check git history]",
        "rotation_instructions": "https://api.slack.com/apps → Your App → Basic Information → Regenerate",
        "update_locations": [
            "GitHub Secrets SLACK_SIGNING_SECRET",
            "Railway",
            "local .env",
        ],
        "rotated": False,
    },
    "slack_webhook": {
        "name": "Slack Webhook URL",
        "old_value": "[REDACTED - check git history]",
        "rotation_instructions": "Slack → Apps → Incoming Webhooks → Delete old, create new",
        "update_locations": [
            "GitHub Secrets SLACK_WEBHOOK_URL",
            "Railway",
            "local .env",
        ],
        "rotated": False,
    },
    "lda_api_key": {
        "name": "LDA API Key",
        "old_value": "[REDACTED - check git history]",
        "rotation_instructions": "Request new key from https://lda.senate.gov/api/",
        "update_locations": ["GitHub Secrets LDA_API_KEY", "Railway", "local .env"],
        "rotated": False,
    },
    "congress_api_key": {
        "name": "Congress API Key",
        "old_value": "[REDACTED - check git history]",
        "rotation_instructions": "Regenerate at https://api.congress.gov/sign-up/",
        "update_locations": [
            "GitHub Secrets CONGRESS_API_KEY",
            "Railway",
            "local .env",
        ],
        "rotated": False,
    },
    "regulations_gov_api_key": {
        "name": "Regulations.gov API Key",
        "old_value": "[REDACTED - check git history]",
        "rotation_instructions": "Regenerate at https://open.gsa.gov/api/regulationsgov/",
        "update_locations": [
            "GitHub Secrets REGULATIONS_GOV_API_KEY",
            "Railway",
            "local .env",
        ],
        "rotated": False,
    },
}


def load_status() -> Dict:
    """Load rotation status from file."""
    if CHECKLIST_FILE.exists():
        with open(CHECKLIST_FILE, "r") as f:
            return json.load(f)
    return CREDENTIALS.copy()


def save_status(status: Dict) -> None:
    """Save rotation status to file."""
    with open(CHECKLIST_FILE, "w") as f:
        json.dump(status, f, indent=2)


def show_status() -> None:
    """Show current rotation status."""
    status = load_status()
    rotated = sum(1 for cred in status.values() if cred.get("rotated", False))
    total = len(status)

    print("=" * 70)
    print(f"Credential Rotation Status: {rotated}/{total} completed")
    print("=" * 70)
    print()

    for key, cred in status.items():
        status_icon = "✅" if cred.get("rotated", False) else "❌"
        print(f"{status_icon} {cred['name']}")
        if not cred.get("rotated", False):
            print(f"   Instructions: {cred['rotation_instructions']}")
            print(f"   Update in: {', '.join(cred['update_locations'])}")
        print()


def mark_rotated(key: str) -> None:
    """Mark a credential as rotated."""
    status = load_status()
    if key in status:
        status[key]["rotated"] = True
        save_status(status)
        print(f"✅ Marked {status[key]['name']} as rotated")
    else:
        print(f"❌ Unknown credential key: {key}")


def main() -> None:
    """Main entry point."""
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "mark" and len(sys.argv) > 2:
            mark_rotated(sys.argv[2])
        elif command == "status":
            show_status()
        elif command == "list":
            status = load_status()
            print("Available credential keys:")
            for key in status.keys():
                print(f"  - {key}")
        else:
            print("Usage:")
            print("  python rotation-checklist.py status    # Show status")
            print("  python rotation-checklist.py mark <key>  # Mark as rotated")
            print("  python rotation-checklist.py list     # List all keys")
    else:
        show_status()


if __name__ == "__main__":
    main()
