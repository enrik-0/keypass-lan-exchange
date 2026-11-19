"""Tracks whether the clipboard still holds the secret copied from KeePassXC.

Pure logic (no Qt, no Windows APIs) so it can be unit-tested anywhere.
The caller supplies the current clipboard sequence number.
"""


class ClipboardGuard:
    def __init__(self):
        self._sequence = None

    def mark(self, sequence):
        """Remember the clipboard sequence right after a KeePassXC copy."""
        self._sequence = sequence

    def clear(self):
        """Forget the copy (after sending, or when the user cancels)."""
        self._sequence = None

    def is_valid(self, current_sequence):
        """True only if the clipboard has not changed since the marked copy."""
        return self._sequence is not None and current_sequence == self._sequence
