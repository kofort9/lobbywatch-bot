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

    # Import and run the v2 server mode
    from bot.run_v2 import main as v2_main

    # Override sys.argv to pass server mode only (let Flask handle port from env)
    sys.argv = ["main.py", "--mode", "server"]

    v2_main()


if __name__ == "__main__":
    main()
