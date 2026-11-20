import base64
import hashlib
import tempfile
import unittest
from pathlib import Path

from aliases import AliasStore, clean_alias, peer_ident, MAX_LEN


class TestAliases(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / 'aliases.json'

    def test_set_get_and_persist(self):
        store = AliasStore(self.path)
        store.set('abcdef0123456789', 'Pepe')
        self.assertEqual(AliasStore(self.path).get('abcdef0123456789'), 'Pepe')

    def test_empty_name_removes_alias(self):
        store = AliasStore(self.path)
        store.set('abcdef0123456789', 'Pepe')
        store.set('abcdef0123456789', '   ')
        self.assertIsNone(AliasStore(self.path).get('abcdef0123456789'))

    def test_clean_alias_collapses_whitespace_and_limits_length(self):
        self.assertEqual(clean_alias('  Pepe \n  el   de  casa '), 'Pepe el de casa')
        self.assertEqual(len(clean_alias('x' * 200)), MAX_LEN)

    def test_corrupt_file_is_ignored(self):
        self.path.write_text('{no es json', encoding='utf-8')
        self.assertIsNone(AliasStore(self.path).get('abcdef0123456789'))

    def test_peer_ident_matches_discovery_formula(self):
        raw = bytes(range(32))
        key_b64 = base64.b64encode(raw).decode('ascii')
        self.assertEqual(peer_ident(key_b64), hashlib.sha256(raw).hexdigest()[:16])


if __name__ == '__main__':
    unittest.main()
