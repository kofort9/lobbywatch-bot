"""Slack app integration for interactive LobbyLens features."""

import hashlib
import hmac
# import json  # Unused for now
import logging
import os
import time
# import urllib.parse  # Unused for now
from typing import Any, Dict, List, Optional

import requests

from .config import settings
from .database import DatabaseManager
from .enhanced_digest import EnhancedDigestComputer
from .matching import MatchingService

logger = logging.getLogger(__name__)


class SlackApp:
    """Handles Slack app interactions including slash commands and events."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.matching_service = MatchingService(db_manager)
        self.digest_computer = EnhancedDigestComputer(db_manager)

        # Slack app credentials (need to be set in environment)
        self.bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.signing_secret = os.getenv("SLACK_SIGNING_SECRET")

        # Track pending confirmations
        self.pending_confirmations: Dict[str, Any] = {}

    def verify_slack_request(self, headers: Dict[str, str], body: str) -> bool:
        """Verify that request came from Slack with proper signature validation."""
        if not self.signing_secret:
            # In production, this should be an error
            if settings.is_production():
                logger.error("SLACK_SIGNING_SECRET not set in production!")
                return False
            else:
                logger.warning(
                    "SLACK_SIGNING_SECRET not set, skipping verification (dev mode)"
                )
                return True

        timestamp = headers.get("X-Slack-Request-Timestamp", "")
        signature = headers.get("X-Slack-Signature", "")

        if not timestamp or not signature:
            logger.warning("Missing Slack signature headers")
            return False

        try:
            # Check timestamp is recent (within 5 minutes)
            request_timestamp = int(timestamp)
            if abs(time.time() - request_timestamp) > 300:
                logger.warning("Slack request timestamp too old")
                return False
        except ValueError:
            logger.warning("Invalid Slack request timestamp")
            return False

        # Create signature
        sig_basestring = f"v0:{timestamp}:{body}"
        expected_signature = (
            "v0="
            + hmac.new(
                self.signing_secret.encode(), sig_basestring.encode(), hashlib.sha256
            ).hexdigest()
        )

        is_valid = hmac.compare_digest(expected_signature, signature)
        if not is_valid:
            logger.warning("Invalid Slack request signature")

        return is_valid

    def post_message(
        self, channel: str, text: str, thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """Post message to Slack channel."""
        if not self.bot_token:
            logger.error("SLACK_BOT_TOKEN not set")
            return {"ok": False, "error": "no_token"}

        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "channel": channel,
            "text": text,
            "unfurl_links": True,
            "unfurl_media": True,
        }

        if thread_ts:
            payload["thread_ts"] = thread_ts

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            result = response.json()
            return (
                result
                if isinstance(result, dict)
                else {"ok": False, "error": "invalid_response"}
            )
        except Exception as e:
            logger.error(f"Failed to post Slack message: {e}")
            return {"ok": False, "error": str(e)}

    def handle_slash_command(self, command_data: Dict[str, Any]) -> Dict[str, str]:
        """Handle slash command from Slack."""
        command = command_data.get("command", "")
        text = command_data.get("text", "").strip()
        channel_id = command_data.get("channel_id", "")
        user_id = command_data.get("user_id", "")

        logger.info(
            f"Slash command: {command} {text} in channel {channel_id} by user {user_id}"
        )

        if command == "/watchlist":
            return self._handle_watchlist_command(text, channel_id, user_id)
        elif command == "/threshold":
            return self._handle_threshold_command(text, channel_id, user_id)
        elif command == "/summary":
            return self._handle_summary_command(text, channel_id, user_id)
        elif command == "/lobbylens":
            return self._handle_lobbylens_command(text, channel_id, user_id)
        elif command == "/lobbypulse":
            return self._handle_lobbypulse_command(text, channel_id, user_id)
        else:
            return {"response_type": "ephemeral", "text": f"Unknown command: {command}"}

    def _handle_watchlist_command(
        self, text: str, channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle /watchlist command."""
        if not text:
            return {
                "response_type": "ephemeral",
                "text": "Usage: `/watchlist add [name]`, `/watchlist remove [name]`, or `/watchlist list`",
            }

        parts = text.split(" ", 1)
        action = parts[0].lower()

        if action == "list":
            return self._handle_watchlist_list(channel_id)
        elif action == "add" and len(parts) > 1:
            return self._handle_watchlist_add(parts[1], channel_id, user_id)
        elif action == "remove" and len(parts) > 1:
            return self._handle_watchlist_remove(parts[1], channel_id)
        else:
            return {
                "response_type": "ephemeral",
                "text": "Usage: `/watchlist add [name]`, `/watchlist remove [name]`, or `/watchlist list`",
            }

    def _handle_watchlist_list(self, channel_id: str) -> Dict[str, str]:
        """Handle watchlist list command."""
        watchlist = self.db_manager.get_channel_watchlist(channel_id)

        if not watchlist:
            return {
                "response_type": "ephemeral",
                "text": "📝 Watchlist is empty. Use `/watchlist add [name]` to add entities.",
            }

        lines = ["📝 **Current Watchlist:**"]

        # Group by type
        by_type: Dict[str, List[Dict[str, Any]]] = {}
        for item in watchlist:
            item_type = item["entity_type"]
            if item_type not in by_type:
                by_type[item_type] = []
            by_type[item_type].append(item)

        for entity_type, items in by_type.items():
            type_name = entity_type.title() + "s"
            lines.append(f"\n*{type_name}:*")
            for item in items:
                score_text = (
                    f" ({item['fuzzy_score']:.0f}% match)"
                    if item["fuzzy_score"] < 100
                    else ""
                )
                lines.append(f"• {item['display_name']}{score_text}")

        return {"response_type": "ephemeral", "text": "\n".join(lines)}

    def _handle_watchlist_add(
        self, search_term: str, channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle watchlist add command."""
        result = self.matching_service.process_watchlist_add(channel_id, search_term)

        if result["status"] == "success":
            return {"response_type": "in_channel", "text": result["message"]}
        elif result["status"] == "no_match":
            return {"response_type": "ephemeral", "text": result["message"]}
        elif result["status"] == "confirmation_needed":
            # Store pending confirmation
            confirmation_key = f"{channel_id}:{user_id}:{int(time.time())}"
            self.pending_confirmations[confirmation_key] = {
                "search_term": result["search_term"],
                "candidates": result["candidates"],
                "channel_id": channel_id,
                "user_id": user_id,
                "timestamp": time.time(),
            }

            # Post message asking for confirmation
            message = result["message"] + f"\n\n_Confirmation key: {confirmation_key}_"

            return {"response_type": "ephemeral", "text": message}
        else:
            return {"response_type": "ephemeral", "text": result["message"]}

    def _handle_watchlist_remove(
        self, search_term: str, channel_id: str
    ) -> Dict[str, str]:
        """Handle watchlist remove command."""
        success = self.db_manager.remove_from_watchlist(channel_id, search_term)

        if success:
            return {
                "response_type": "in_channel",
                "text": f"✅ Removed **{search_term}** from watchlist.",
            }
        else:
            return {
                "response_type": "ephemeral",
                "text": f"❌ **{search_term}** not found in watchlist.",
            }

    def _is_admin_user(self, user_id: str) -> bool:
        """Check if user is admin."""
        admin_users = settings.get_admin_users()
        return (
            not admin_users or user_id in admin_users
        )  # If no admins configured, everyone is admin

    def _handle_threshold_command(
        self, text: str, channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle /threshold command."""
        # Admin check for threshold changes
        if text and not self._is_admin_user(user_id):
            return {
                "response_type": "ephemeral",
                "text": "❌ Only admins can modify thresholds. Contact your channel admin.",
            }

        if not text:
            settings = self.db_manager.get_channel_settings(channel_id)
            return {
                "response_type": "ephemeral",
                "text": f"Current thresholds:\n• Filings: {settings['threshold_filings']}\n• Amount: ${settings['threshold_amount']:,}\n\nUsage: `/threshold set filings [number]` or `/threshold set amount [number]`",
            }

        parts = text.split()
        if len(parts) != 3 or parts[0] != "set":
            return {
                "response_type": "ephemeral",
                "text": "Usage: `/threshold set filings [number]` or `/threshold set amount [number]`",
            }

        threshold_type = parts[1].lower()
        try:
            value = int(parts[2])
        except ValueError:
            return {
                "response_type": "ephemeral",
                "text": "Threshold value must be a number.",
            }

        if threshold_type == "filings":
            self.db_manager.update_channel_setting(
                channel_id, "threshold_filings", value
            )
            return {
                "response_type": "in_channel",
                "text": f"✅ Mini-digest filing threshold set to **{value}**.",
            }
        elif threshold_type == "amount":
            self.db_manager.update_channel_setting(
                channel_id, "threshold_amount", value
            )
            return {
                "response_type": "in_channel",
                "text": f"✅ Alert amount threshold set to **${value:,}**.",
            }
        else:
            return {
                "response_type": "ephemeral",
                "text": "Threshold type must be 'filings' or 'amount'.",
            }

    def _handle_summary_command(
        self, text: str, channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle /summary command."""
        # Admin check for summary setting changes
        if text and not self._is_admin_user(user_id):
            return {
                "response_type": "ephemeral",
                "text": "❌ Only admins can modify summary settings. Contact your channel admin.",
            }

        if not text or text.lower() not in ["on", "off"]:
            settings = self.db_manager.get_channel_settings(channel_id)
            status = "ON" if settings["show_descriptions"] else "OFF"
            return {
                "response_type": "ephemeral",
                "text": f"Filing descriptions are currently **{status}**.\n\nUsage: `/summary on` or `/summary off`",
            }

        show_descriptions = text.lower() == "on"
        self.db_manager.update_channel_setting(
            channel_id, "show_descriptions", show_descriptions
        )

        status = "ON" if show_descriptions else "OFF"
        return {
            "response_type": "in_channel",
            "text": f"✅ Filing descriptions turned **{status}**.",
        }

    def _handle_lobbylens_command(
        self, text: str, channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle /lobbylens command for manual digest generation."""
        if text.lower() == "digest":
            # Generate manual digest
            try:
                digest = self.digest_computer.compute_enhanced_digest(
                    channel_id, "daily"
                )

                # Post digest to channel
                result = self.post_message(channel_id, digest)

                if result.get("ok"):
                    return {
                        "response_type": "ephemeral",
                        "text": "✅ Manual digest generated and posted to channel.",
                    }
                else:
                    return {
                        "response_type": "ephemeral",
                        "text": f"❌ Failed to post digest: {result.get('error', 'Unknown error')}",
                    }
            except Exception as e:
                logger.error(f"Manual digest generation failed: {e}")
                return {
                    "response_type": "ephemeral",
                    "text": f"❌ Failed to generate digest: {e}",
                }
        else:
            return {
                "response_type": "ephemeral",
                "text": "🔍 **LobbyLens Commands:**\n"
                "• `/lobbypulse` - Generate fresh lobbying digest\n"
                "• `/watchlist` - Manage watchlist entities\n"
                "• `/threshold` - Set alert thresholds\n"
                "• `/summary` - Toggle filing descriptions\n"
                "• `/lobbylens digest` - Generate manual digest\n\n"
                "_Use `/lobbypulse help` for detailed usage._",
            }

    def handle_message_event(
        self, event_data: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """Handle message events (for confirmation responses)."""
        if event_data.get("type") != "message" or event_data.get("bot_id"):
            return None  # Skip non-messages and bot messages

        text = event_data.get("text", "").strip()
        channel_id = event_data.get("channel", "")
        user_id = event_data.get("user", "")

        # Look for confirmation key in message
        confirmation_key = None
        for key in self.pending_confirmations:
            if key in text:
                confirmation_key = key
                break

        if not confirmation_key:
            return None  # Not a confirmation response

        confirmation = self.pending_confirmations.get(confirmation_key)
        if (
            not confirmation
            or confirmation["channel_id"] != channel_id
            or confirmation["user_id"] != user_id
        ):
            return None

        # Check if confirmation is still valid (within 10 minutes)
        if time.time() - confirmation["timestamp"] > 600:
            del self.pending_confirmations[confirmation_key]
            return None

        # Extract response from message (remove confirmation key)
        response = text.replace(confirmation_key, "").strip()

        # Process confirmation response
        result = self.matching_service.process_confirmation_response(
            channel_id=confirmation["channel_id"],
            search_term=confirmation["search_term"],
            candidates=confirmation["candidates"],
            response=response,
        )

        # Clean up confirmation
        del self.pending_confirmations[confirmation_key]

        # Post result to channel
        self.post_message(channel_id, result["message"])

        return result

    def _handle_lobbypulse_command(
        self, text: str, channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle /lobbypulse command for manual digest generation."""
        # Parse digest type from text
        digest_type = "daily"  # Default
        if text:
            text_lower = text.lower().strip()
            if text_lower in ["daily", "mini"]:
                digest_type = text_lower
            elif text_lower in ["help", "?"]:
                return {
                    "response_type": "ephemeral",
                    "text": "💓 **LobbyPulse Commands:**\n"
                    "• `/lobbypulse` - Generate daily digest\n"
                    "• `/lobbypulse daily` - Generate daily digest\n"
                    "• `/lobbypulse mini` - Generate mini digest\n"
                    "• `/lobbypulse help` - Show this help\n\n"
                    "_This won't affect your scheduled morning/afternoon digests._",
                }
            else:
                return {
                    "response_type": "ephemeral",
                    "text": f"❌ Unknown option: `{text}`\n"
                    "Use `/lobbypulse help` for available options.",
                }

        # Generate and send digest
        try:
            logger.info(
                f"Manual {digest_type} digest requested by {user_id} in {channel_id}"
            )

            # Generate digest
            digest = self.digest_computer.compute_enhanced_digest(
                channel_id, digest_type
            )

            # Post to channel
            result = self.post_message(channel_id, digest)

            if result.get("ok", False):
                return {
                    "response_type": "in_channel",
                    "text": f"💓 **LobbyPulse {digest_type.title()} Digest** generated successfully!",
                }
            else:
                return {
                    "response_type": "ephemeral",
                    "text": f"❌ Failed to generate {digest_type} digest. Please try again.",
                }

        except Exception as e:
            logger.error(f"Error generating manual {digest_type} digest: {e}")
            return {
                "response_type": "ephemeral",
                "text": f"❌ Error generating {digest_type} digest: {str(e)}",
            }

    def send_digest(self, channel_id: str, digest_type: str = "daily") -> bool:
        """Send digest to a channel."""
        try:
            digest = self.digest_computer.compute_enhanced_digest(
                channel_id, digest_type
            )
            result = self.post_message(channel_id, digest)
            return bool(result.get("ok", False))
        except Exception as e:
            logger.error(f"Failed to send {digest_type} digest to {channel_id}: {e}")
            return False

    def send_alert(self, channel_id: str, message: str) -> bool:
        """Send alert message to a channel."""
        try:
            alert_text = f"🚨 **LobbyLens Alert**\n\n{message}"
            result = self.post_message(channel_id, alert_text)
            return bool(result.get("ok", False))
        except Exception as e:
            logger.error(f"Failed to send alert to {channel_id}: {e}")
            return False


def create_slack_app(db_manager: DatabaseManager) -> SlackApp:
    """Factory function to create Slack app instance."""
    return SlackApp(db_manager)
