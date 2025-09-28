"""Web server for handling Slack events and slash commands."""

import json
import logging
from typing import Dict, Any

from flask import Flask, request, jsonify, make_response

logger = logging.getLogger(__name__)


def create_web_server(slack_app) -> Flask:
    """Create Flask web server for Slack integration."""
    
    app = Flask(__name__)
    
    @app.route('/', methods=['GET'])
    def root():
        """Root endpoint."""
        return jsonify({'service': 'lobbylens', 'status': 'running'})
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        return jsonify({'status': 'healthy', 'service': 'lobbylens'})
    
    @app.route('/lobbylens/health', methods=['GET'])
    def lobbylens_health_check():
        """LobbyLens specific health check endpoint."""
        return jsonify({'status': 'healthy', 'service': 'lobbylens'})
    
    @app.route('/lobbylens/commands', methods=['POST'])
    def handle_slash_command():
        """Handle Slack slash commands."""
        try:
            # Verify request came from Slack
            if not slack_app.verify_slack_request(dict(request.headers), request.get_data(as_text=True)):
                logger.warning("Invalid Slack request signature")
                return make_response("Unauthorized", 401)
            
            # Parse command data
            command_data = {
                'command': request.form.get('command'),
                'text': request.form.get('text', ''),
                'channel_id': request.form.get('channel_id'),
                'channel_name': request.form.get('channel_name'),
                'user_id': request.form.get('user_id'),
                'user_name': request.form.get('user_name'),
                'response_url': request.form.get('response_url'),
                'trigger_id': request.form.get('trigger_id')
            }
            
            # Handle command
            response = slack_app.handle_slash_command(command_data)
            
            return jsonify(response)
        
        except Exception as e:
            logger.error(f"Error handling slash command: {e}")
            return jsonify({
                'response_type': 'ephemeral',
                'text': f'Sorry, something went wrong: {e}'
            })
    
    @app.route('/lobbylens/events', methods=['POST'])
    def handle_slack_event():
        """Handle Slack events."""
        try:
            data = request.get_json()
            
            # Handle URL verification challenge
            if data.get('type') == 'url_verification':
                return jsonify({'challenge': data.get('challenge')})
            
            # Verify request came from Slack  
            if not slack_app.verify_slack_request(dict(request.headers), request.get_data(as_text=True)):
                logger.warning("Invalid Slack event signature")
                return make_response("Unauthorized", 401)
            
            # Handle event
            event = data.get('event', {})
            if event:
                result = slack_app.handle_message_event(event)
                if result:
                    logger.info(f"Handled message event: {result['status']}")
            
            return make_response("OK", 200)
        
        except Exception as e:
            logger.error(f"Error handling Slack event: {e}")
            return make_response("Internal Server Error", 500)
    
    @app.route('/lobbylens/digest/manual/<channel_id>', methods=['POST'])
    def manual_digest(channel_id: str):
        """Trigger manual digest for a channel."""
        try:
            digest_type = request.args.get('type', 'daily')
            
            success = slack_app.send_digest(channel_id, digest_type)
            
            if success:
                return jsonify({'status': 'success', 'message': f'{digest_type.title()} digest sent'})
            else:
                return jsonify({'status': 'error', 'message': 'Failed to send digest'}), 500
        
        except Exception as e:
            logger.error(f"Error sending manual digest: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    return app
