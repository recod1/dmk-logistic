from __future__ import annotations

from unittest import TestCase

from mobile_api.route_incidents import format_incident_chat, next_return_stage


class ReturnStageTests(TestCase):
    def test_starts_with_issued(self) -> None:
        self.assertEqual(next_return_stage(""), "issued")

    def test_walks_to_delivered(self) -> None:
        self.assertEqual(next_return_stage("issued"), "loaded")
        self.assertEqual(next_return_stage("loaded"), "departed")
        self.assertEqual(next_return_stage("gates"), "delivered")
        self.assertIsNone(next_return_stage("delivered"))

    def test_chat_text_includes_reason(self) -> None:
        text = format_incident_chat(kind="delay", comment="пробка")
        self.assertIn("Опоздание", text)
        self.assertIn("пробка", text)

    def test_return_chat_includes_cargo(self) -> None:
        text = format_incident_chat(
            kind="return",
            comment="брак",
            cargo_name="корма",
            quantity="4 паллеты",
            authorized_by="Иванов",
            return_stage="issued",
        )
        self.assertIn("Возврат", text)
        self.assertIn("корма", text)
        self.assertIn("4 паллеты", text)
        self.assertIn("Иванов", text)
        self.assertIn("Оформил возврат", text)
