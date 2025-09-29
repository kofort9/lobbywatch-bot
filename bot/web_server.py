"""Web server for handling Slack events and slash commands with v2 system."""

# Removed unused import
import logging
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request

logger = logging.getLogger(__name__)


def create_web_server(slack_app: Optional[Any] = None) -> Flask:
    """Create Flask web server for v2 Slack integration."""

    app = Flask(__name__)

    # Import v2 components (will be consolidated)
    from bot.run import run_daily_digest, run_mini_digest
    from bot.signals_database import SignalsDatabaseV2

    database = SignalsDatabaseV2()

    @app.route("/", methods=["GET"])
    def root() -> Any:
        """Root endpoint."""
        return jsonify(
            {
                "service": "lobbylens-v2",
                "status": "running",
                "version": "2.0.0",
                "features": [
                    "industry_snapshots",
                    "priority_scoring",
                    "mobile_formatting",
                    "watchlist_alerts",
                ],
            }
        )

    @app.route("/health", methods=["GET"])
    def health_check() -> Any:
        """Health check endpoint."""
        return jsonify({"status": "healthy", "service": "lobbylens-v2"})

    @app.route("/lobbylens/health", methods=["GET"])
    def lobbylens_health_check() -> Any:
        """LobbyLens specific health check endpoint."""
        return jsonify({"status": "healthy", "service": "lobbylens-v2"})

    @app.route("/lobbylens/commands", methods=["POST"])
    def handle_slash_command() -> Any:
        """Handle Slack slash commands."""
        try:
            # Parse command data
            command_data = {
                "command": request.form.get("command"),
                "text": request.form.get("text", ""),
                "channel_id": request.form.get("channel_id") or "",
                "channel_name": request.form.get("channel_name"),
                "user_id": request.form.get("user_id"),
                "user_name": request.form.get("user_name"),
                "team_id": request.form.get("team_id"),
            }

            logger.info(f"Received command: {command_data}")

            # Route commands
            response = handle_command(command_data)
            return jsonify(response)

        except Exception as e:
            logger.error(f"Error handling slash command: {e}")
            return jsonify(
                {
                    "response_type": "ephemeral",
                    "text": f"Error processing command: {str(e)}",
                }
            )

    @app.route("/lobbylens/events", methods=["POST"])
    def handle_events() -> Any:
        """Handle Slack events."""
        try:
            # Handle URL verification
            if request.json and request.json.get("type") == "url_verification":
                return request.json.get("challenge")

            # Handle other events
            event_data = request.json
            logger.info(f"Received event: {event_data}")

            return jsonify({"status": "ok"})

        except Exception as e:
            logger.error(f"Error handling event: {e}")
            return jsonify({"status": "error", "message": str(e)})

    @app.route("/lobbylens/digest/manual/<channel_id>", methods=["POST"])
    def manual_digest(channel_id: str) -> Any:
        """Manual digest endpoint for testing."""
        try:
            # Get digest type from request
            data = request.get_json() or {}
            digest_type = data.get("type", "daily")
            hours_back = int(data.get("hours", 24))

            digest: Optional[str] = None
            if digest_type == "daily":
                digest = run_daily_digest(hours_back, channel_id)
            elif digest_type == "mini":
                digest = run_mini_digest(hours_back, channel_id)
                if not digest:
                    return jsonify({"message": "Mini-digest thresholds not met"})
            else:
                return jsonify({"error": "Invalid digest type"})

            # Ensure digest is a string
            digest_text = digest or "No digest content available"

            return jsonify(
                {
                    "digest": digest_text,
                    "type": digest_type,
                    "channel_id": channel_id,
                    "hours_back": hours_back,
                }
            )

        except Exception as e:
            logger.error(f"Error generating manual digest: {e}")
            return jsonify({"error": str(e)})

    def handle_command(command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle individual slash commands."""
        command = command_data.get("command", "")
        text = command_data.get("text", "").strip()
        channel_id = command_data.get("channel_id", "")

        if command == "/lobbypulse":
            return handle_lobbypulse_command(text, channel_id)
        elif command == "/lobbylens":
            return handle_lobbylens_command(text, channel_id)
        elif command == "/watchlist":
            return handle_watchlist_command(text, channel_id)
        elif command == "/threshold":
            return handle_threshold_command(text, channel_id)
        else:
            return {
                "response_type": "ephemeral",
                "text": f"Unknown command: {command}",
            }

    def handle_lobbypulse_command(text: str, channel_id: str) -> Dict[str, Any]:
        """Handle /lobbypulse command."""
        if text == "help":
            return {
                "response_type": "in_channel",
                "text": "🔍 **LobbyLens Commands**\n\n"
                "**Digest Commands:**\n"
                "• `/lobbypulse` - Generate daily digest (24h)\n"
                "• `/lobbypulse mini` - Generate mini digest (4h)\n"
                "• `/lobbypulse help` - Show this help\n\n"
                "**Watchlist Commands:**\n"
                "• `/watchlist add <entity>` - Add entity to watchlist\n"
                "• `/watchlist remove <entity>` - Remove entity from watchlist\n"
                "• `/watchlist list` - Show current watchlist\n\n"
                "**Settings Commands:**\n"
                "• `/threshold set <number>` - Set mini-digest threshold\n"
                "• `/threshold` - Show current threshold settings\n\n"
                "**System Commands:**\n"
                "• `/lobbylens` - Show system status and stats\n"
                "• `/lobbylens help` - Show system help\n\n"
                "**Examples:**\n"
                "• `/watchlist add Google`\n"
                "• `/threshold set 5`\n"
                "• `/lobbypulse mini`",
            }
        elif text == "mini":
            try:
                digest = run_mini_digest(4, channel_id)
                if digest:
                    return {"response_type": "in_channel", "text": digest}
                else:
                    return {
                        "response_type": "ephemeral",
                        "text": "No mini-digest - thresholds not met",
                    }
            except Exception as e:
                return {
                    "response_type": "ephemeral",
                    "text": f"Error generating mini digest: {str(e)}",
                }
        else:
            try:
                digest = run_daily_digest(24, channel_id)
                return {"response_type": "in_channel", "text": digest}
            except Exception as e:
                return {
                    "response_type": "ephemeral",
                    "text": f"Error generating digest: {str(e)}",
                }

    def handle_lobbylens_command(text: str, channel_id: str) -> Dict[str, Any]:
        """Handle /lobbylens command."""
        if text == "help":
            return {
                "response_type": "in_channel",
                "text": "🔍 **LobbyLens v2 System Help**\n\n"
                "**What is LobbyLens?**\n"
                "LobbyLens monitors daily government activity and provides "
                "digestible signals about bills, regulations, hearings, and "
                "regulatory actions.\n\n"
                "**Key Features:**\n"
                "• 📰 Daily government signals digest (24h)\n"
                "• ⚡ Mini digest alerts (4h, when thresholds met)\n"
                "• 🎯 Watchlist alerts for specific entities\n"
                "• 📊 Priority scoring and industry mapping\n"
                "• 📱 Mobile-friendly formatting\n"
                "• 🏭 Industry snapshots and trend analysis\n\n"
                "**Data Sources:**\n"
                "• Congress API (bills, hearings, votes)\n"
                "• Federal Register (rules, regulations)\n"
                "• Regulations.gov (dockets, comment periods)\n\n"
                "**Quick Start:**\n"
                "1. `/lobbypulse` - Get your first digest\n"
                "2. `/watchlist add <entity>` - Add entities to watch\n"
                "3. `/threshold set 5` - Set mini-digest threshold\n\n"
                "**Need Help?**\n"
                "• `/lobbypulse help` - Show all commands\n"
                "• `/lobbylens` - Show system status",
            }
        else:
            # Get system stats
            stats = database.get_signal_stats()
            return {
                "response_type": "in_channel",
                "text": f"🔍 **LobbyLens v2 Status**\n\n"
                f"**Database Stats:**\n"
                f"• Total signals: {stats['total_signals']}\n"
                f"• High priority: {stats['high_priority']}\n"
                f"• Watchlist hits: {stats['watchlist_hits']}\n\n"
                f"**Sources:** {', '.join(stats['by_source'].keys())}\n"
                f"**Industries:** {', '.join(list(stats['by_industry'].keys())[:5])}",
            }

    def handle_watchlist_command(text: str, channel_id: str) -> Dict[str, Any]:
        """Handle /watchlist command."""
        parts = text.split(" ", 1)
        action = parts[0].lower() if parts else ""

        if action == "add" and len(parts) > 1:
            entity = parts[1].strip()
            if database.add_watchlist_item(channel_id, entity):
                return {
                    "response_type": "in_channel",
                    "text": f"✅ Added '{entity}' to watchlist",
                }
            else:
                return {
                    "response_type": "ephemeral",
                    "text": f"❌ Failed to add '{entity}' to watchlist",
                }
        elif action == "remove" and len(parts) > 1:
            entity = parts[1].strip()
            if database.remove_watchlist_item(channel_id, entity):
                return {
                    "response_type": "in_channel",
                    "text": f"✅ Removed '{entity}' from watchlist",
                }
            else:
                return {
                    "response_type": "ephemeral",
                    "text": f"❌ Failed to remove '{entity}' from watchlist",
                }
        elif action == "list":
            watchlist = database.get_watchlist(channel_id)
            if watchlist:
                items = "\n".join([f"• {item}" for item in watchlist])
                return {
                    "response_type": "in_channel",
                    "text": f"📋 **Watchlist for #{channel_id}**\n\n{items}",
                }
            else:
                return {
                    "response_type": "in_channel",
                    "text": f"📋 **Watchlist for #{channel_id}**\n\n"
                    "No items in watchlist",
                }
        else:
            return {
                "response_type": "ephemeral",
                "text": "Usage: `/watchlist add <entity>`, "
                "`/watchlist remove <entity>`, or `/watchlist list`",
            }

    def handle_threshold_command(text: str, channel_id: str) -> Dict[str, Any]:
        """Handle /threshold command."""
        parts = text.split(" ", 1)
        action = parts[0].lower() if parts else ""

        if action == "set" and len(parts) > 1:
            try:
                threshold = int(parts[1].strip())
                if database.update_channel_setting(
                    channel_id, "mini_digest_threshold", threshold
                ):
                    return {
                        "response_type": "in_channel",
                        "text": f"✅ Set mini-digest threshold to {threshold} signals",
                    }
                else:
                    return {
                        "response_type": "ephemeral",
                        "text": "❌ Failed to update threshold",
                    }
            except ValueError:
                return {
                    "response_type": "ephemeral",
                    "text": "❌ Threshold must be a number",
                }
        else:
            settings = database.get_channel_settings(channel_id)
            return {
                "response_type": "in_channel",
                "text": f"📊 **Threshold Settings for #{channel_id}**\n\n"
                f"• Mini-digest threshold: "
                f"{settings['mini_digest_threshold']} signals\n"
                f"• High-priority threshold: {settings['high_priority_threshold']}\n"
                f"• Surge threshold: {settings['surge_threshold']}%\n\n"
                f"Usage: `/threshold set <number>`",
            }

    return app
