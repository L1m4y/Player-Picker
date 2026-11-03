import unittest

from playerpicker.slots import SlotError, SlotTable


class SlotTableTests(unittest.TestCase):
    def setUp(self):
        self.table = SlotTable(4)

    def test_add_uses_lowest_free_slot(self):
        self.assertEqual(self.table.add("/dev/input/event1", "Pad 1"), 0)
        self.assertEqual(self.table.add("/dev/input/event2", "Pad 2"), 1)
        self.assertEqual(self.table.slot_of("/dev/input/event1"), 0)

    def test_add_returns_none_when_full(self):
        for index in range(4):
            self.assertEqual(self.table.add(f"/dev/input/event{index}", f"Pad {index}"), index)
        self.assertIsNone(self.table.add("/dev/input/event9", "Pad 9"))
        self.assertEqual(len(self.table), 4)

    def test_add_duplicate_raises(self):
        self.table.add("/dev/input/event1", "Pad 1")
        with self.assertRaises(SlotError):
            self.table.add("/dev/input/event1", "Pad 1")

    def test_remove_frees_slot_and_returns_it(self):
        self.table.add("/dev/input/event1", "Pad 1")
        self.table.add("/dev/input/event2", "Pad 2")
        self.assertEqual(self.table.remove("/dev/input/event1"), 0)
        self.assertIsNone(self.table.slot_of("/dev/input/event1"))
        self.assertEqual(self.table.add("/dev/input/event3", "Pad 3"), 0)
        self.assertIsNone(self.table.remove("/dev/input/event99"))

    def test_move_to_free_slot(self):
        self.table.add("/dev/input/event1", "Pad 1")
        changed = self.table.move("/dev/input/event1", 2)
        self.assertEqual(changed, {0, 2})
        self.assertEqual(self.table.slot_of("/dev/input/event1"), 2)
        self.assertIsNone(self.table.device_at(0))

    def test_move_to_occupied_slot_swaps(self):
        self.table.add("/dev/input/event1", "Pad 1")
        self.table.add("/dev/input/event2", "Pad 2")
        changed = self.table.move("/dev/input/event1", 1)
        self.assertEqual(changed, {0, 1})
        self.assertEqual(self.table.slot_of("/dev/input/event1"), 1)
        self.assertEqual(self.table.slot_of("/dev/input/event2"), 0)

    def test_move_to_same_slot_is_noop(self):
        self.table.add("/dev/input/event1", "Pad 1")
        self.assertEqual(self.table.move("/dev/input/event1", 0), set())

    def test_move_validation(self):
        self.table.add("/dev/input/event1", "Pad 1")
        for slot in (-1, 4, "1", None, True):
            with self.assertRaises(SlotError):
                self.table.move("/dev/input/event1", slot)
        with self.assertRaises(SlotError):
            self.table.move("/dev/input/event99", 0)

    def test_snapshot_is_ordered_by_slot(self):
        self.table.add("/dev/input/event1", "Pad 1")
        self.table.add("/dev/input/event2", "Pad 2")
        self.table.move("/dev/input/event1", 3)
        self.assertEqual(
            self.table.snapshot(),
            [
                {"path": "/dev/input/event2", "name": "Pad 2", "slot": 1},
                {"path": "/dev/input/event1", "name": "Pad 1", "slot": 3},
            ],
        )
        self.assertIsNone(self.table.device_at(0))

    def test_invalid_slot_count(self):
        for count in (0, -1, True, "4"):
            with self.assertRaises(ValueError):
                SlotTable(count)


if __name__ == "__main__":
    unittest.main()
