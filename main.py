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
    # Get port from environment, handling Railway's variable expansion
    port_env = os.environ.get('PORT', '8000')
    
    # Railway sometimes passes '$PORT' as literal string, handle this case
    if port_env == '$PORT':
        print("Warning: Got literal '$PORT', using default port 8000")
        port = 8000
    else:
        try:
            port = int(port_env)
        except (ValueError, TypeError):
            print(f"Warning: Invalid PORT value '{port_env}', using default port 8000")
            port = 8000
    
    print(f"Starting LobbyLens web server on port {port}")
    
    # Import and run the enhanced server mode
    from bot.enhanced_run import main as enhanced_main
    
    # Override sys.argv to pass server mode and port
    sys.argv = ['main.py', '--mode', 'server', '--port', str(port)]
    
    enhanced_main()

if __name__ == '__main__':
    main()
