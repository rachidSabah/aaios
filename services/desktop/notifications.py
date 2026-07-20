"""Native Notification Service — platform-abstracted desktop notifications.

This service publishes notifications through the Event Bus so any subscriber
(including the Mission Control UI, system tray, or third-party plugins) can
observe and respond. The platform adapter takes care of the actual OS-level
toast/notification call so the business logic stays portable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.event_bus import get_bus
from core.logging import get_logger

_log = get_logger(__name__)


@dataclass
class DesktopNotification:
    """A desktop notification payload."""
    id: str
    title: str
    message: str
    level: str = "info"  # info, warning, error, success
    category: str = "general"  # general, update, system, plugin, task
    source: str = "system"
    timestamp: str = ""
    actions: list[dict[str, str]] = field(default_factory=list)
    persistent: bool = False
    dismissed: bool = False


class NativeNotificationService:
    """Publish and display desktop notifications through the Event Bus."""

    def __init__(self, app_name: str = "AAiOS") -> None:
        self.app_name = app_name
        self._history: list[DesktopNotification] = []
        self._max_history: int = 500

    async def notify(
        self,
        title: str,
        message: str,
        *,
        level: str = "info",
        category: str = "general",
        source: str = "system",
        actions: list[dict[str, str]] | None = None,
        persistent: bool = False,
    ) -> DesktopNotification:
        """Create and publish a desktop notification."""
        notification = DesktopNotification(
            id=str(uuid4()),
            title=title,
            message=message,
            level=level,
            category=category,
            source=source,
            timestamp=datetime.now(UTC).isoformat(),
            actions=actions or [],
            persistent=persistent,
        )
        self._history.append(notification)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        try:
            bus = get_bus()
            await bus.publish(Event(
                topic="desktop.notification",
                correlation_id=uuid4(),
                actor=ActorRef.system(),
                payload={
                    "id": notification.id,
                    "title": notification.title,
                    "message": notification.message,
                    "level": notification.level,
                    "category": notification.category,
                    "source": notification.source,
                    "timestamp": notification.timestamp,
                    "persistent": notification.persistent,
                },
            ))
        except Exception:  # noqa: BLE001
            pass

        _log.info("desktop.notification.sent", title=title, level=level, category=category)
        return notification

    async def dismiss(self, notification_id: str) -> bool:
        for n in self._history:
            if n.id == notification_id:
                n.dismissed = True
                return True
        return False

    def history(
        self,
        *,
        limit: int = 100,
        level: str | None = None,
        category: str | None = None,
    ) -> list[DesktopNotification]:
        results = list(self._history)
        if level:
            results = [n for n in results if n.level == level]
        if category:
            results = [n for n in results if n.category == category]
        return results[-limit:]

    def as_dict(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "total": len(self._history),
            "recent": [
                {"id": n.id, "title": n.title, "level": n.level,
                 "category": n.category, "timestamp": n.timestamp,
                 "dismissed": n.dismissed}
                for n in self._history[-20:]
            ],
        }

    async def shutdown(self) -> None:
        self._history.clear()
        _log.info("desktop.notifications.shutdown")
