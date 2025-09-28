"""Base notifier interface."""

from abc import ABC, abstractmethod
from typing import Protocol


class Notifier(Protocol):
    """Protocol for notification services."""
    
    def send(self, text: str) -> None:
        """Send a notification message.
        
        Args:
            text: The message text to send
            
        Raises:
            NotificationError: If the notification fails to send
        """
        ...


class NotificationError(Exception):
    """Raised when a notification fails to send."""
    pass
