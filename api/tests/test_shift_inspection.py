from __future__ import annotations

from unittest import TestCase

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
