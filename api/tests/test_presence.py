from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import TestCase

from mobile_api.presence import connection_label, connection_status


class PresenceStatusTests(TestCase):
    def test_fresh_heartbeat_is_online(self) -> None:
        now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(connection_status(now - timedelta(seconds=20), now=now), "online")
        self.assertEqual(connection_label("online"), "Есть интернет")

    def test_stale_heartbeat_is_offline(self) -> None:
        now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(connection_status(now - timedelta(minutes=4), now=now), "offline")
        self.assertEqual(connection_label("offline"), "Нет интернета")
