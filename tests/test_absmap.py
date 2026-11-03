import unittest

from playerpicker.absmap import AbsAxis


class AbsAxisTests(unittest.TestCase):
    def test_identity_range(self):
        axis = AbsAxis(0, -32768, 32767, -32768, 32767)
        for value in (-32768, -1, 0, 1, 32767):
            self.assertEqual(axis.scale(value), value)

    def test_unipolar_stick_is_expanded(self):
        axis = AbsAxis(0, 0, 255, -32768, 32767)
        self.assertEqual(axis.scale(0), -32768)
        self.assertEqual(axis.scale(255), 32767)
        self.assertEqual(axis.scale(128), 128)

    def test_trigger_is_reduced(self):
        axis = AbsAxis(0, 0, 1023, 0, 255)
        self.assertEqual(axis.scale(0), 0)
        self.assertEqual(axis.scale(511), 127)
        self.assertEqual(axis.scale(1023), 255)

    def test_clamps(self):
        axis = AbsAxis(0, 0, 255, 0, 255)
        self.assertEqual(axis.scale(-10), 0)
        self.assertEqual(axis.scale(999), 255)

    def test_degenerate_source_range(self):
        axis = AbsAxis(0, 5, 5, 0, 255)
        self.assertEqual(axis.scale(5), 0)
        self.assertEqual(axis.scale(6), 255)


if __name__ == "__main__":
    unittest.main()
