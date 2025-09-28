#!/usr/bin/env python3
"""
LobbyLens main entry point for Railway deployment.

Railway's Nixpacks will automatically run `python main.py` when this file is present.
This starts the Flask web server to handle Slack interactions.
"""

import os
import sys

def main():
    """Start LobbyLens web server for Railway deployment."""
    print("Starting LobbyLens web server...")
    
    # Import and run the enhanced server mode
    from bot.enhanced_run import main as enhanced_main
    
    # Override sys.argv to pass server mode only (let Flask handle port from env)
    sys.argv = ['main.py', '--mode', 'server']
    
    enhanced_main()

if __name__ == '__main__':
    main()
