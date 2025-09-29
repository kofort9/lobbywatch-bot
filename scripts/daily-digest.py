#!/usr/bin/env python3
"""
Daily Digest CLI - Run LobbyLens V2 daily government activity digest

This script collects signals from government APIs and sends a formatted digest to Slack.
Designed to run in GitHub Actions or other CI/CD environments.
"""

import os
import sys
import logging
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run daily digest collection and posting."""
    print("🔄 Starting LobbyLens V2 Daily Digest...")
    print(f"📅 Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    
    try:
        # Import V2 system components
        from bot.daily_signals import DailySignalsCollector
        from bot.digest import DigestFormatter
        from bot.notifiers.slack import SlackNotifier
        from bot.config import settings
        
        print("✅ V2 system imports successful")
        
        # Initialize V2 components
        config = settings.model_dump()
        collector = DailySignalsCollector(config)
        formatter = DigestFormatter()
        
        print("✅ V2 components initialized")
        
        # Collect signals from all sources
        print("📡 Collecting signals from government APIs...")
        print("  - Congress API (bills, hearings, committee activities)")
        print("  - Federal Register API (rules, notices, regulatory actions)")
        print("  - Regulations.gov API (dockets, comments, deadlines)")
        
        signals = collector.collect_signals(hours_back=24)
        print(f"✅ Collected {len(signals)} signals")
        
        # Show signal breakdown
        if signals:
            sources = {}
            for signal in signals:
                sources[signal.source] = sources.get(signal.source, 0) + 1
            
            for source, count in sources.items():
                print(f"  - {source}: {count} signals")
        
        # Format digest
        print("📝 Formatting daily digest...")
        digest = formatter.format_daily_digest(signals, hours_back=24)
        print(f"✅ Generated digest: {len(digest)} characters")
        
        # Send to Slack
        slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        if slack_webhook:
            print("📤 Sending digest to Slack...")
            notifier = SlackNotifier(slack_webhook)
            notifier.send(digest)
            print("✅ Digest sent successfully to Slack!")
        else:
            print("⚠️ No SLACK_WEBHOOK_URL configured")
            print("📋 Digest preview:")
            print("=" * 60)
            preview = digest[:1000] + "\n\n[...truncated...]" if len(digest) > 1000 else digest
            print(preview)
            print("=" * 60)
        
        # Summary
        print("\n🎉 Daily digest completed successfully!")
        print(f"📊 Summary:")
        print(f"  - Signals collected: {len(signals)}")
        print(f"  - Digest length: {len(digest)} characters")
        print(f"  - Slack delivery: {'✅ Success' if slack_webhook else '⚠️ Skipped (no webhook)'}")
        
        return 0
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure all dependencies are installed: pip install -e .")
        return 1
        
    except Exception as e:
        print(f"❌ Error during digest generation: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
