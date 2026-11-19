import socket
import threading
import unittest
from cryptography.hazmat.primitives.asymmetric import ed25519
from secure_protocol import handshake


class TestProtocol(unittest.TestCase):
    def test_two_way_authenticated_encryption_and_sas(self):
        one, two = socket.socketpair()
        ca = ed25519.Ed25519PrivateKey.generate()
        sa = ed25519.Ed25519PrivateKey.generate()
        received = []

        def server():
            with two:
                hs = handshake(two, sa, 'receiver', is_client=False)
                received.append(hs.sas)
                self.assertEqual(hs.channel.recv(), {'type': 'secret', 'value': 'ejemplo'})
                hs.channel.send({'type': 'result', 'ok': True})

        t = threading.Thread(target=server)
        t.start()
        with one:
            hs = handshake(one, ca, 'sender', is_client=True)
            hs.channel.send({'type': 'secret', 'value': 'ejemplo'})
            self.assertEqual(hs.channel.recv(), {'type': 'result', 'ok': True})
        t.join(timeout=5)
        self.assertFalse(t.is_alive())
        self.assertEqual(received, [hs.sas])
        self.assertEqual(len(hs.sas), 8)


if __name__ == '__main__':
    unittest.main()
