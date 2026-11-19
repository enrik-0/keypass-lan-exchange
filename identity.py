"""Long-term identity stored in Windows Credential Manager through keyring."""
import json
import os
import threading
from pathlib import Path

import keyring
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

SERVICE = 'KeePassLANShare-v1'
USER = 'device-ed25519'


def get_identity():
    if os.name != 'nt':
        raise RuntimeError('Esta aplicación solo admite Windows (almacén de credenciales).')
    stored = keyring.get_password(SERVICE, USER)
    if stored:
        return ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(stored))
    identity = ed25519.Ed25519PrivateKey.generate()
    raw = identity.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                 serialization.NoEncryption())
    keyring.set_password(SERVICE, USER, raw.hex())
    if keyring.get_password(SERVICE, USER) != raw.hex():
        raise RuntimeError('No se ha podido conservar la identidad en Credential Manager.')
    return identity


class TrustStore:
    def __init__(self):
        self.path = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'KeePassLANShare' / 'peers.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.peers = json.loads(self.path.read_text('utf-8')) if self.path.exists() else {}

    def get(self, key):
        with self.lock:
            return self.peers.get(key)

    def add(self, key, name):
        with self.lock:
            self.peers[key] = name
            self._save()

    def remove(self, key):
        with self.lock:
            self.peers.pop(key, None)
            self._save()

    def _save(self):
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.peers, indent=2, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, self.path)
