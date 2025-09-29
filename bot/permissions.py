"""Permission management for LobbyLens commands."""

import logging
import os
from typing import Dict, List, Optional, Set
import requests

logger = logging.getLogger(__name__)


class PermissionManager:
    """Manages permissions for LobbyLens commands."""
    
    def __init__(self, slack_token: Optional[str] = None):
        self.slack_token = slack_token or os.getenv("SLACK_BOT_TOKEN")
        self._admin_cache: Dict[str, Set[str]] = {}  # channel_id -> set of admin user_ids
        self._cache_ttl = 300  # 5 minutes
        self._last_cache_update: Dict[str, float] = {}
    
    def is_channel_admin(self, channel_id: str, user_id: str) -> bool:
        """Check if user is an admin in the given channel.
        
        Args:
            channel_id: Slack channel ID
            user_id: Slack user ID
            
        Returns:
            True if user is channel admin, False otherwise
        """
        try:
            # Check cache first
            import time
            now = time.time()
            
            if (channel_id in self._admin_cache and 
                channel_id in self._last_cache_update and
                now - self._last_cache_update[channel_id] < self._cache_ttl):
                return user_id in self._admin_cache[channel_id]
            
            # Fetch fresh admin list
            admins = self._fetch_channel_admins(channel_id)
            self._admin_cache[channel_id] = admins
            self._last_cache_update[channel_id] = now
            
            return user_id in admins
            
        except Exception as e:
            logger.error(f"Failed to check channel admin status: {e}")
            # Fail open - allow if we can't check
            return True
    
    def _fetch_channel_admins(self, channel_id: str) -> Set[str]:
        """Fetch channel admins from Slack API.
        
        Args:
            channel_id: Slack channel ID
            
        Returns:
            Set of admin user IDs
        """
        if not self.slack_token:
            logger.warning("No Slack token available for permission check")
            return set()
        
        try:
            # Get channel info to determine if it's a public channel or private group
            info_response = requests.get(
                "https://slack.com/api/conversations.info",
                headers={"Authorization": f"Bearer {self.slack_token}"},
                params={"channel": channel_id},
                timeout=10
            )
            
            if not info_response.ok:
                logger.error(f"Failed to get channel info: {info_response.status_code}")
                return set()
            
            info_data = info_response.json()
            if not info_data.get("ok"):
                logger.error(f"Slack API error getting channel info: {info_data.get('error')}")
                return set()
            
            channel = info_data.get("channel", {})
            
            # Get channel members with their roles
            members_response = requests.get(
                "https://slack.com/api/conversations.members",
                headers={"Authorization": f"Bearer {self.slack_token}"},
                params={"channel": channel_id},
                timeout=10
            )
            
            if not members_response.ok:
                logger.error(f"Failed to get channel members: {members_response.status_code}")
                return set()
            
            members_data = members_response.json()
            if not members_data.get("ok"):
                logger.error(f"Slack API error getting members: {members_data.get('error')}")
                return set()
            
            # For now, consider channel creator and workspace admins as admins
            admins = set()
            
            # Add channel creator if available
            creator = channel.get("creator")
            if creator:
                admins.add(creator)
            
            # Get workspace admins/owners
            team_response = requests.get(
                "https://slack.com/api/users.list",
                headers={"Authorization": f"Bearer {self.slack_token}"},
                params={"limit": 1000},  # Get all users
                timeout=10
            )
            
            if team_response.ok:
                team_data = team_response.json()
                if team_data.get("ok"):
                    for member in team_data.get("members", []):
                        # Add workspace admins and owners
                        if member.get("is_admin") or member.get("is_owner"):
                            admins.add(member["id"])
            
            logger.info(f"Found {len(admins)} admins for channel {channel_id}")
            return admins
            
        except Exception as e:
            logger.error(f"Error fetching channel admins: {e}")
            return set()
    
    def get_configured_admins(self, channel_id: str) -> List[str]:
        """Get configured admins for a channel from environment or database.
        
        This allows manual configuration of admins via environment variables
        as a fallback when Slack API permissions are insufficient.
        
        Args:
            channel_id: Slack channel ID
            
        Returns:
            List of admin user IDs
        """
        # Check environment variable for manual admin configuration
        env_key = f"CHANNEL_ADMINS_{channel_id.upper()}"
        env_admins = os.getenv(env_key)
        if env_admins:
            return [admin.strip() for admin in env_admins.split(",")]
        
        # Check global admin list
        global_admins = os.getenv("LOBBYLENS_ADMINS")
        if global_admins:
            return [admin.strip() for admin in global_admins.split(",")]
        
        return []
    
    def can_post_digest(self, channel_id: str, user_id: str) -> bool:
        """Check if user can post digests in the given channel.
        
        Args:
            channel_id: Slack channel ID
            user_id: Slack user ID
            
        Returns:
            True if user can post digests, False otherwise
        """
        # Check configured admins first (manual override)
        configured_admins = self.get_configured_admins(channel_id)
        if configured_admins and user_id in configured_admins:
            return True
        
        # Check Slack channel admin status
        return self.is_channel_admin(channel_id, user_id)
    
    def get_permission_error_message(self, command: str) -> str:
        """Get error message for permission denied.
        
        Args:
            command: The command that was denied
            
        Returns:
            Error message string
        """
        return (
            f"🔒 Permission denied for `{command}`. "
            "Only channel admins can post LDA digests. "
            "Data queries are available to all members."
        )


# Global instance
_permission_manager = None

def get_permission_manager() -> PermissionManager:
    """Get the global permission manager instance."""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager
