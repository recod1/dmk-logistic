from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import TestCase

from mobile_api.presence import (
    SAMPLE_INTERVAL_SEC,
    availability_status,
    connection_label,
    connection_status,
)


class PresenceStatusTests(TestCase):
    def test_fresh_heartbeat_is_online(self) -> None:
        now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(connection_status(now - timedelta(seconds=20), now=now), "online")
        self.assertEqual(connection_label("online"), "Доступен")
        self.assertEqual(connection_label("recent"), "Доступен")

    def test_stale_heartbeat_is_offline(self) -> None:
        now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(connection_status(now - timedelta(minutes=4), now=now), "offline")
        self.assertEqual(connection_label("offline"), "Недоступен")

    def test_recent_heartbeat_counts_as_available(self) -> None:
        now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(connection_status(now - timedelta(minutes=2), now=now), "recent")
        self.assertEqual(availability_status("recent"), "online")
        self.assertEqual(connection_label("recent"), "Доступен")

    def test_presence_history_interval_is_five_minutes(self) -> None:
        self.assertEqual(SAMPLE_INTERVAL_SEC, 300)
