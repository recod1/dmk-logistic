from unittest import TestCase

from utils.vehicle_plate import is_valid_plate, normalize_plate, require_plate


class VehiclePlateTests(TestCase):
    def test_std_and_spec(self) -> None:
        self.assertEqual(require_plate("а123вс77"), "А123ВС77")
        self.assertEqual(require_plate("A123BC777"), "А123ВС777")
        self.assertEqual(require_plate("ен068477"), "ЕН068477")

    def test_rejects_garbage(self) -> None:
        self.assertFalse(is_valid_plate("123"))
        self.assertFalse(is_valid_plate(""))

    def test_strips_spaces(self) -> None:
        self.assertEqual(normalize_plate("А 123 ВС 77"), "А123ВС77")
