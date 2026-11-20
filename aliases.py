"""Local nicknames for nearby devices.

Aliases are stored only on this PC, keyed by the device identifier that
discovery already exposes (the first 16 hex chars of SHA-256 over the
device's Ed25519 public key). They are never sent over the network, and
they do not change the device's real name.
"""
import base64
import hashlib
import json
import os
import threading
from pathlib import Path

MAX_LEN = 40


def peer_ident(key_b64):
    """Device identifier for a base64 Ed25519 public key (same as Discovery uses)."""
    return hashlib.sha256(base64.b64decode(key_b64)).hexdigest()[:16]


def clean_alias(name):
    """Collapse whitespace and cut to MAX_LEN. Empty result means 'remove alias'."""
    return ' '.join(name.split())[:MAX_LEN]


class AliasStore:
    def __init__(self, path=None):
        if path is None:
            path = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'KeePassLANShare' / 'aliases.json'
        self.path = Path(path)
        self.lock = threading.RLock()
        self.names = {}
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text('utf-8'))
                if isinstance(data, dict):
                    self.names = {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
        except (OSError, ValueError):
            self.names = {}

    def get(self, ident):
        with self.lock:
            return self.names.get(ident)

    def set(self, ident, name):
        name = clean_alias(name)
        with self.lock:
            if name:
                self.names[ident] = name
            else:
                self.names.pop(ident, None)
            self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.names, indent=2, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, self.path)
