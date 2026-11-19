import unittest

from clipboard_guard import ClipboardGuard


class TestClipboardGuard(unittest.TestCase):
    def test_invalid_without_copy(self):
        guard = ClipboardGuard()
        self.assertFalse(guard.is_valid(10))

    def test_valid_while_sequence_unchanged(self):
        guard = ClipboardGuard()
        guard.mark(10)
        self.assertTrue(guard.is_valid(10))

    def test_invalid_after_clipboard_changed(self):
        guard = ClipboardGuard()
        guard.mark(10)
        self.assertFalse(guard.is_valid(11))

    def test_clear_invalidates(self):
        guard = ClipboardGuard()
        guard.mark(10)
        guard.clear()
        self.assertFalse(guard.is_valid(10))


if __name__ == '__main__':
    unittest.main()
