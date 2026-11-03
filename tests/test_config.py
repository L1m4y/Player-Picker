import os
import tempfile
import unittest
from pathlib import Path

from playerpicker.config import (
    DEFAULT_SLOT_COUNT,
    DEFAULT_SOCKET_PATH,
    ICONS_ENV,
    SLOTS_ENV,
    SOCKET_ENV,
    ConfigError,
    parse_slot_count,
    resolve_icon_dir,
    socket_path,
)


class ParseSlotCountTests(unittest.TestCase):
    def test_default(self):
        self.assertEqual(parse_slot_count(None), DEFAULT_SLOT_COUNT)
        self.assertEqual(parse_slot_count("   "), DEFAULT_SLOT_COUNT)

    def test_valid(self):
        self.assertEqual(parse_slot_count("1"), 1)
        self.assertEqual(parse_slot_count("8"), 8)
        self.assertEqual(parse_slot_count(4), 4)

    def test_invalid(self):
        for value in ("0", "9", "-1", "abc", "4.5", 3.7, True, False):
            with self.assertRaises(ConfigError):
                parse_slot_count(value)

    def test_error_mentions_env(self):
        with self.assertRaises(ConfigError) as context:
            parse_slot_count("99")
        self.assertIn(SLOTS_ENV, str(context.exception))


class SocketPathTests(unittest.TestCase):
    def test_default(self):
        self.assertEqual(socket_path({}), DEFAULT_SOCKET_PATH)
        self.assertEqual(socket_path({SOCKET_ENV: "  "}), DEFAULT_SOCKET_PATH)

    def test_override(self):
        from playerpicker.config import SOCKET_ENV

        self.assertEqual(socket_path({SOCKET_ENV: "/tmp/test.sock"}), "/tmp/test.sock")


class IconDirTests(unittest.TestCase):
    def test_override(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(resolve_icon_dir({ICONS_ENV: directory}), Path(directory))

    def test_missing_override_falls_back(self):
        missing = os.path.join(tempfile.gettempdir(), "playerpicker-icons-missing")
        self.assertTrue(resolve_icon_dir({ICONS_ENV: missing}).is_dir())


if __name__ == "__main__":
    unittest.main()
