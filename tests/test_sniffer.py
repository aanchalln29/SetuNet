"""Unit tests for the capture layer (packet model, filters, sniffer plumbing)."""

import unittest

from src.capture.packet import PacketRecord, sha256_hex
from src.capture.filters import PacketFilter, build_bpf
from src.capture.sniffer import PacketSniffer


class TestPacketRecord(unittest.TestCase):
    def test_hash_computed_from_payload(self):
        pkt = PacketRecord(seq=1, src_ip="10.0.0.1", dst_ip="10.0.0.2",
                           payload=b"hello")
        self.assertEqual(pkt.payload_hash, sha256_hex(b"hello"))
        self.assertEqual(pkt.size, len(b"hello"))

    def test_flow_key(self):
        pkt = PacketRecord(seq=1, src_ip="10.0.0.1", dst_ip="10.0.0.2",
                           src_port=1234, dst_port=443, protocol="TCP")
        self.assertEqual(pkt.flow_key, ("10.0.0.1", "10.0.0.2", 1234, 443, "TCP"))

    def test_public_dict_omits_payload(self):
        pkt = PacketRecord(seq=1, src_ip="a", dst_ip="b", payload=b"secret")
        d = pkt.to_public_dict()
        self.assertNotIn("payload", d)
        self.assertIn("payload_hash", d)


class TestFilters(unittest.TestCase):
    def test_build_bpf(self):
        bpf = build_bpf(protocols=["tcp", "udp"], ports=[443], hosts=["10.0.0.1"])
        self.assertIn("tcp or udp", bpf)
        self.assertIn("port 443", bpf)
        self.assertIn("host 10.0.0.1", bpf)

    def test_protocol_filter(self):
        f = PacketFilter(protocols={"TCP"})
        tcp = PacketRecord(seq=1, src_ip="10.0.0.1", dst_ip="10.0.0.2", protocol="TCP")
        udp = PacketRecord(seq=2, src_ip="10.0.0.1", dst_ip="10.0.0.2", protocol="UDP")
        self.assertTrue(f.allows(tcp))
        self.assertFalse(f.allows(udp))

    def test_cidr_filter(self):
        f = PacketFilter(cidrs=["10.0.0.0/24"])
        inside = PacketRecord(seq=1, src_ip="10.0.0.5", dst_ip="8.8.8.8")
        outside = PacketRecord(seq=2, src_ip="192.168.1.1", dst_ip="1.1.1.1")
        self.assertTrue(f.allows(inside))
        self.assertFalse(f.allows(outside))

    def test_size_bounds(self):
        f = PacketFilter(min_size=100, max_size=1000)
        small = PacketRecord(seq=1, src_ip="a", dst_ip="b", size=50)
        ok = PacketRecord(seq=2, src_ip="a", dst_ip="b", size=500)
        self.assertFalse(f.allows(small))
        self.assertTrue(f.allows(ok))


class TestSniffer(unittest.TestCase):
    def test_feed_invokes_callback(self):
        received = []
        sniffer = PacketSniffer(on_packet=received.append)
        pkt = PacketRecord(seq=1, src_ip="10.0.0.1", dst_ip="10.0.0.2")
        sniffer.feed(pkt)
        self.assertEqual(len(received), 1)
        self.assertIs(received[0], pkt)

    def test_start_without_scapy_returns_false(self):
        # On a box without scapy, start() degrades gracefully to simulation mode.
        sniffer = PacketSniffer(on_packet=lambda p: None)
        if not sniffer.available:
            self.assertFalse(sniffer.start())


if __name__ == "__main__":
    unittest.main()
