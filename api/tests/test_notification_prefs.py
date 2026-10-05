from unittest import TestCase

from mobile_api.notification_kinds import KIND_CHAT, KIND_POINT, KIND_ROUTES, notification_kind, pref_allows


class _Pref:
    def __init__(self, mute_point=False, mute_chat=False, mute_routes=False):
        self.mute_point = mute_point
        self.mute_chat = mute_chat
        self.mute_routes = mute_routes


class NotificationKindTests(TestCase):
    def test_kinds(self) -> None:
        self.assertEqual(notification_kind("point_status_stale"), KIND_POINT)
        self.assertEqual(notification_kind("chat_message"), KIND_CHAT)
        self.assertEqual(notification_kind("route_created"), KIND_ROUTES)
        self.assertEqual(notification_kind("point_status_changed"), KIND_ROUTES)

    def test_mute_flags(self) -> None:
        pref = _Pref(mute_chat=True)
        self.assertTrue(pref_allows(None, KIND_CHAT))
        self.assertFalse(pref_allows(pref, KIND_CHAT))
        self.assertTrue(pref_allows(pref, KIND_POINT))
        self.assertTrue(pref_allows(pref, KIND_ROUTES))
