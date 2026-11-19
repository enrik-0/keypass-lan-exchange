"""Authenticated, end-to-end encrypted single-session protocol, v1.

Ephemeral X25519 keys and Ed25519 long-term signatures, HKDF-SHA256,
AES-256-GCM with directional sequence counters. Both endpoints compare
an 8-digit SAS on first pairing to authenticate long-term identities.
"""
import base64
import hashlib
import hmac
import json
import os
import socket
import struct
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAX_FRAME = 128 * 1024
VERSION = 1


def b64(data):
    return base64.b64encode(data).decode('ascii')


def un64(data):
    return base64.b64decode(data, validate=True)


def canonical(obj):
    return json.dumps(obj, ensure_ascii=True, separators=(',', ':'), sort_keys=True).encode('ascii')


def raw_pub(key):
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def recv_exact(sock, n):
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError('La conexión se ha cerrado.')
        data.extend(chunk)
    return bytes(data)


def send_frame(sock, payload):
    if len(payload) > MAX_FRAME:
        raise ValueError('Mensaje demasiado grande.')
    sock.sendall(struct.pack('!I', len(payload)) + payload)


def recv_frame(sock):
    n = struct.unpack('!I', recv_exact(sock, 4))[0]
    if n > MAX_FRAME or n == 0:
        raise ValueError('Tamaño de mensaje no permitido.')
    return recv_exact(sock, n)


def send_json(sock, obj):
    send_frame(sock, canonical(obj))


def recv_json(sock):
    result = json.loads(recv_frame(sock))
    if not isinstance(result, dict):
        raise ValueError('Formato de mensaje no válido.')
    return result


@dataclass
class Handshake:
    channel: object
    peer_key: str
    peer_name: str
    sas: str


class SecureChannel:
    def __init__(self, sock, tx_key, rx_key, tx_prefix, rx_prefix):
        self.sock = sock
        self.tx = AESGCM(tx_key)
        self.rx = AESGCM(rx_key)
        self.tx_prefix = tx_prefix
        self.rx_prefix = rx_prefix
        self.sent = 0
        self.received = 0

    def send(self, msg):
        if self.sent >= 2**64:
            raise ValueError('Límite de secuencia alcanzado.')
        nonce = self.tx_prefix + self.sent.to_bytes(8, 'big')
        self.sent += 1
        send_frame(self.sock, self.tx.encrypt(nonce, canonical(msg), b'KPC1'))

    def recv(self):
        if self.received >= 2**64:
            raise ValueError('Límite de secuencia alcanzado.')
        nonce = self.rx_prefix + self.received.to_bytes(8, 'big')
        raw = self.rx.decrypt(nonce, recv_frame(self.sock), b'KPC1')
        self.received += 1
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError('Mensaje no válido.')
        return obj


def handshake(sock, identity, name, is_client):
    """Authenticate the handshake; trust pinning is performed by the caller."""
    ephemeral = x25519.X25519PrivateKey.generate()
    hello = {
        'v': VERSION,
        'name': name[:64],
        'ed': b64(raw_pub(identity.public_key())),
        'x': b64(raw_pub(ephemeral.public_key())),
        'nonce': b64(os.urandom(32)),
    }
    if is_client:
        send_json(sock, hello)
        other = recv_json(sock)
        c, s = hello, other
    else:
        other = recv_json(sock)
        send_json(sock, hello)
        c, s = other, hello
    if other.get('v') != VERSION or not isinstance(other.get('name'), str):
        raise ValueError('Versión de protocolo o identidad incorrecta.')
    if len(other['name']) > 64:
        raise ValueError('Nombre de equipo demasiado largo.')
    peer_ed_raw, peer_x_raw, peer_nonce = (un64(other[k]) for k in ('ed', 'x', 'nonce'))
    if len(peer_ed_raw) != 32 or len(peer_x_raw) != 32 or len(peer_nonce) != 32:
        raise ValueError('Claves o nonce no válidos.')
    transcript = canonical({'client': c, 'server': s})
    role = b'client' if is_client else b'server'
    peer_role = b'server' if is_client else b'client'
    own_signature = identity.sign(b'KPC1|signature|' + role + b'|' + transcript)
    if is_client:
        peer_sig = recv_json(sock)
        if set(peer_sig) != {'sig'}:
            raise ValueError('Firma inválida.')
        ed25519.Ed25519PublicKey.from_public_bytes(peer_ed_raw).verify(
            un64(peer_sig['sig']), b'KPC1|signature|' + peer_role + b'|' + transcript)
        send_json(sock, {'sig': b64(own_signature)})
    else:
        send_json(sock, {'sig': b64(own_signature)})
        peer_sig = recv_json(sock)
        if set(peer_sig) != {'sig'}:
            raise ValueError('Firma inválida.')
        ed25519.Ed25519PublicKey.from_public_bytes(peer_ed_raw).verify(
            un64(peer_sig['sig']), b'KPC1|signature|' + peer_role + b'|' + transcript)
    secret = ephemeral.exchange(x25519.X25519PublicKey.from_public_bytes(peer_x_raw))
    key = HKDF(algorithm=hashes.SHA256(), length=64, salt=hashlib.sha256(transcript).digest(),
               info=b'KPC1|session-v1').derive(secret)
    sas_num = int.from_bytes(hmac.new(key, b'KPC1|sas|' + transcript, hashlib.sha256).digest()[:8], 'big') % (10**8)
    if is_client:
        channel = SecureChannel(sock, key[:32], key[32:], b'CLNT', b'SRVR')
    else:
        channel = SecureChannel(sock, key[32:], key[:32], b'SRVR', b'CLNT')
    return Handshake(channel, other['ed'], other['name'], f'{sas_num:08d}')
