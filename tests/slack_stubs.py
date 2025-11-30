"""Test helpers that mimic SlackApp behaviour without external dependencies."""

from __future__ import annotations

from typing import Any, Dict

import bot.web_server as web_server


class StubSlackApp:
    """Lightweight stand-in for SlackApp command handling."""

    def __init__(self) -> None:
        self.watchlist: list[str] = []
        self.database: Any = None

    def set_database(self, database: Any) -> None:
        """Attach a database object when provided by the server factory."""
        self.database = database

    def handle_slash_command(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        command = (command_data.get("command") or "").strip()
        text = (command_data.get("text") or "").strip()
        channel_id = command_data.get("channel_id") or ""

        if command == "/lobbypulse":
            return self._handle_lobbypulse(text, channel_id)
        if command == "/lobbylens":
            return {
                "response_type": "in_channel",
                "text": (
                    "🔍 **LobbyLens v2 Status**\n\n"
                    "• Total signals: 0\n"
                    "• High priority (24h): 0\n"
                    "• Recent signals (24h): 0\n"
                    "• Average priority: 0.0"
                ),
            }
        if command == "/watchlist":
            return self._handle_watchlist(text, channel_id)
        if command == "/threshold":
            return self._handle_threshold(text, channel_id)
        if command == "/summary":
            return {"response_type": "ephemeral", "text": "Not implemented in stub"}

        return {
            "response_type": "ephemeral",
            "text": f"Unknown command: {command}",
        }

    def handle_message_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return success for message events to keep flow simple."""
        return {"status": "ok", "event": event_data}

    def _handle_lobbypulse(self, text: str, channel_id: str) -> Dict[str, Any]:
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

        if text == "mini":
            digest = web_server.run_mini_digest(4, channel_id)
            if digest:
                return {"response_type": "in_channel", "text": digest}
            return {
                "response_type": "ephemeral",
                "text": "No mini-digest - thresholds not met",
            }

        try:
            digest = web_server.run_daily_digest(24, channel_id)
            return {"response_type": "in_channel", "text": digest}
        except Exception as exc:  # pragma: no cover - defensive
            return {
                "response_type": "ephemeral",
                "text": f"Error generating digest: {exc}",
            }

    def _handle_watchlist(self, text: str, channel_id: str) -> Dict[str, Any]:
        parts = text.split(" ", 1) if text else []
        action = parts[0].lower() if parts else ""

        if action == "add" and len(parts) > 1:
            entity = parts[1].strip()
            if self.database and hasattr(self.database, "add_watchlist_item"):
                success = self.database.add_watchlist_item(channel_id, entity)
                if success:
                    self.watchlist.append(entity)
                return {
                    "response_type": "in_channel" if success else "ephemeral",
                    "text": (
                        f"✅ Added '{entity}' to watchlist"
                        if success
                        else f"❌ Failed to add '{entity}' to watchlist"
                    ),
                }

            self.watchlist.append(entity)
            return {
                "response_type": "in_channel",
                "text": f"✅ Added '{entity}' to watchlist",
            }
        if action == "remove" and len(parts) > 1:
            entity = parts[1].strip()
            if self.database and hasattr(self.database, "remove_watchlist_item"):
                success = self.database.remove_watchlist_item(channel_id, entity)
                if success:
                    self.watchlist = [item for item in self.watchlist if item != entity]
                return {
                    "response_type": "in_channel" if success else "ephemeral",
                    "text": (
                        f"✅ Removed '{entity}' from watchlist"
                        if success
                        else f"❌ Failed to remove '{entity}' from watchlist"
                    ),
                }

            removed = entity in self.watchlist
            self.watchlist = [item for item in self.watchlist if item != entity]
            return {
                "response_type": "in_channel" if removed else "ephemeral",
                "text": (
                    f"✅ Removed '{entity}' from watchlist"
                    if removed
                    else f"❌ Failed to remove '{entity}' from watchlist"
                ),
            }
        if action == "list":
            if self.database and hasattr(self.database, "get_watchlist"):
                watchlist = self.database.get_watchlist(channel_id) or []
            else:
                watchlist = self.watchlist

            if watchlist:
                items = "\n".join([f"• {item}" for item in watchlist])
                return {
                    "response_type": "in_channel",
                    "text": f"📋 **Watchlist for #{channel_id}**\n\n{items}",
                }
            return {
                "response_type": "in_channel",
                "text": f"📋 **Watchlist for #{channel_id}**\n\n"
                "No items in watchlist",
            }

        return {
            "response_type": "ephemeral",
            "text": "Usage: `/watchlist add <entity>`, "
            "`/watchlist remove <entity>`, or `/watchlist list`",
        }

    def _handle_threshold(self, text: str, channel_id: str) -> Dict[str, Any]:
        parts = text.split(" ", 1) if text else []
        action = parts[0].lower() if parts else ""

        if action == "set" and len(parts) > 1:
            try:
                threshold = int(parts[1].strip())
                if self.database and hasattr(self.database, "update_channel_setting"):
                    success = self.database.update_channel_setting(
                        channel_id, "mini_digest_threshold", threshold
                    )
                    if not success:
                        return {
                            "response_type": "ephemeral",
                            "text": "❌ Failed to update threshold",
                        }
                return {
                    "response_type": "in_channel",
                    "text": f"✅ Set mini-digest threshold to {threshold} signals",
                }
            except ValueError:
                return {
                    "response_type": "ephemeral",
                    "text": "❌ Threshold must be a number",
                }

        # Show settings
        if self.database and hasattr(self.database, "get_channel_settings"):
            settings = self.database.get_channel_settings(channel_id)
            mini_threshold = settings.get("mini_digest_threshold", 10)
            high_threshold = settings.get("high_priority_threshold", 5.0)
            surge_threshold = settings.get("surge_threshold", 200.0)
        else:
            mini_threshold = 10
            high_threshold = 5.0
            surge_threshold = 200.0

        return {
            "response_type": "in_channel",
            "text": f"📊 **Threshold Settings for #{channel_id}**\n\n"
            f"• Mini-digest threshold: {mini_threshold} signals\n"
            f"• High-priority threshold: {high_threshold}\n"
            f"• Surge threshold: {surge_threshold}%\n\n"
            "Usage: `/threshold set <number>`",
        }
