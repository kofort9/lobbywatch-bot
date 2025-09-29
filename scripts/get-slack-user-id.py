#!/usr/bin/env python3
"""Helper script to find your Slack user ID for DM alerts."""

import os
import sys

import requests


def get_slack_user_id():
    """Get your Slack user ID for setting up DM alerts."""

    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if not slack_token:
        print("❌ SLACK_BOT_TOKEN environment variable not set")
        print("   Set it to your bot token (xoxb-...)")
        return

    try:
        # Get bot info to show which workspace we're connected to
        auth_response = requests.get(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {slack_token}"},
            timeout=10,
        )

        if auth_response.ok:
            auth_data = auth_response.json()
            if auth_data.get("ok"):
                print(f"✅ Connected to workspace: {auth_data.get('team')}")
                print(f"   Bot user: {auth_data.get('user')}")
            else:
                print(f"❌ Auth failed: {auth_data.get('error')}")
                return

        # Get users list
        print("\n🔍 Fetching users...")
        response = requests.get(
            "https://slack.com/api/users.list",
            headers={"Authorization": f"Bearer {slack_token}"},
            params={"limit": 100},
            timeout=10,
        )

        if not response.ok:
            print(f"❌ HTTP error: {response.status_code}")
            return

        data = response.json()
        if not data.get("ok"):
            print(f"❌ Slack API error: {data.get('error')}")
            return

        # Show users (excluding bots and deleted users)
        users = [
            member
            for member in data.get("members", [])
            if not member.get("deleted", False)
            and not member.get("is_bot", False)
            and member.get("name") != "slackbot"
        ]

        print(f"\n👥 Found {len(users)} active users:")
        print("=" * 60)

        for user in users[:20]:  # Show first 20 users
            user_id = user.get("id")
            name = user.get("name", "unknown")
            real_name = user.get("real_name", "")
            display_name = user.get("profile", {}).get("display_name", "")

            display = real_name or display_name or name
            print(f"   {user_id} - @{name} ({display})")

        if len(users) > 20:
            print(f"   ... and {len(users) - 20} more users")

        print("\n" + "=" * 60)
        print("📋 To set up DM alerts:")
        print("   1. Find your user ID from the list above")
        print("   2. Set environment variable:")
        print("      LOBBYLENS_ADMIN_USER_ID=U1234567890")
        print("   3. Test with:")
        print(
            '      python -c "from bot.alerts import get_alert_manager; get_alert_manager().test_alerts_system()"'
        )

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("🔍 Slack User ID Finder")
    print("=" * 40)
    get_slack_user_id()
