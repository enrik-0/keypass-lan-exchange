import ipaddress
import socket
import unittest
from unittest import mock

import network
from network import Nearby, TransferService


class TestRankAddresses(unittest.TestCase):
    def setUp(self):
        self.local = [ipaddress.ip_network('192.168.1.0/24')]
        patcher = mock.patch.object(network, '_local_networks', return_value=self.local)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_same_subnet_first(self):
        ips = ['10.8.0.2', '192.168.1.20', '172.17.0.1']
        self.assertEqual(network.rank_addresses(ips)[0], '192.168.1.20')

    def test_drops_loopback_and_link_local(self):
        ips = ['127.0.0.1', '169.254.10.10', '192.168.1.5']
        self.assertEqual(network.rank_addresses(ips), ['192.168.1.5'])

    def test_keeps_all_candidates_as_fallback(self):
        ips = ['10.8.0.2', '192.168.1.20']
        self.assertEqual(set(network.rank_addresses(ips)), set(ips))


class TestConnect(unittest.TestCase):
    def test_all_candidates_fail_with_actionable_message(self):
        # Reserve a port and close it so connections are refused immediately.
        probe = socket.socket()
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
        probe.close()
        peer = Nearby('x', 'PC-B', '127.0.0.1', port, 'a' * 16, ('127.0.0.1',))
        with self.assertRaises(ConnectionError) as ctx:
            TransferService._connect(peer)
        self.assertIn('firewall', str(ctx.exception))
        self.assertIn('127.0.0.1', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
