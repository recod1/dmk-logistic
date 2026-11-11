from __future__ import annotations

from unittest import TestCase

from mobile_api.entity_docs import apply_profile_to_shift_docs, collect_writeback, parse_docs
from mobile_api.shift_inspection import analyse, empty_phase, handover_from_intake


class ShiftInspectionTests(TestCase):
    def test_empty_intake_has_required_docs_and_checks(self) -> None:
        phase = empty_phase()
        self.assertGreaterEqual(len(phase["docs"]), 10)
        self.assertGreaterEqual(len(phase["checks"]), 10)

    def test_analyse_flags_missing_truck_and_photos(self) -> None:
        issues = analyse({"driver_name": "", "truck": "", "intake": empty_phase()}, "start", set())
        texts = [text for _, text in issues]
        self.assertTrue(any("водитель" in text.lower() for text in texts))
        self.assertTrue(any("госномер" in text.lower() for text in texts))
        self.assertTrue(any("нет фото" in text.lower() for text in texts))

    def test_handover_copies_docs_without_presence(self) -> None:
        intake = empty_phase()
        intake["docs"][0]["has"] = "y"
        intake["docs"][0]["exp"] = "2027-01-01"
        end = handover_from_intake(intake)
        self.assertEqual(end["docs"][0]["has"], None)
        self.assertEqual(end["docs"][0]["exp"], "2027-01-01")
        self.assertEqual(end["docs"][0]["name"], intake["docs"][0]["name"])


class EntityDocsTests(TestCase):
    def test_profile_fills_empty_shift_docs(self) -> None:
        intake = empty_phase()
        profile = parse_docs('{"license": {"has": "y", "exp": "2027-05-01"}}', "driver")
        apply_profile_to_shift_docs(intake["docs"], profile, "driver")
        license_doc = next(item for item in intake["docs"] if item["name"] == "Водительское удостоверение")
        self.assertEqual(license_doc["has"], "y")
        self.assertEqual(license_doc["exp"], "2027-05-01")
        waybill = next(item for item in intake["docs"] if item["name"] == "Путевой лист")
        self.assertIsNone(waybill["has"])

    def test_writeback_skips_waybill(self) -> None:
        grouped = collect_writeback(
            [
                {"name": "Путевой лист", "has": "y", "exp": "", "d1": "", "d2": "", "kind": ""},
                {"name": "СТС тягача", "has": "y", "exp": "", "d1": "", "d2": "", "kind": ""},
            ]
        )
        self.assertEqual(grouped["vehicle"]["sts"]["has"], "y")
        self.assertFalse(grouped["driver"])
        self.assertNotIn("waybill", grouped["vehicle"])
