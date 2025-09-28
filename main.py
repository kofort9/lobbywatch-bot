#!/usr/bin/env python3
"""
LobbyLens v2 main entry point for Railway deployment.

Railway's Nixpacks will automatically run `python main.py` when this file is present.
This starts the Flask web server v2 to handle Slack interactions.
"""

import os
import sys


def main():
    """Start LobbyLens v2 web server for Railway deployment."""
    print("Starting LobbyLens v2 web server...")
    print("Version: 2.0.0")
    print("Service: lobbylens-v2")
    print("Features: industry_snapshots, priority_scoring, mobile_formatting, watchlist_alerts")

    try:
        # Import and run the web server mode
        from bot.web_server import create_web_server
        print("✅ web_server imported successfully")

        # Create and run the web server
        app = create_web_server()
        
        # Use Railway's dynamic port
        port = int(os.environ.get("PORT", 8000))
        print(f"✅ Starting server on port {port}")
        
        app.run(host="0.0.0.0", port=port, debug=False)
    except Exception as e:
        print(f"❌ Error importing v2_main: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
