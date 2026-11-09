"""Unit tests for the detection engine and the individual detectors."""

import time
import unittest

from src.detection.sequence_tracker import SequenceTracker
from src.detection.spam_detector import SpamDetector
from src.detection.exfil_detector import ExfilDetector


class TestSequenceTracker(unittest.TestCase):
    def test_no_gap_for_contiguous(self):
        t = SequenceTracker(max_gap=3, window_seconds=10)
        now = 1000.0
        for s in range(10):
            t.observe(s, now=now)
        self.assertIsNone(t.gap_exceeded(now=now))

    def test_gap_detected(self):
        t = SequenceTracker(max_gap=3, window_seconds=10)
        now = 1000.0
        t.observe(0, now=now)
        t.observe(6, now=now)          # 1..5 missing => 5 > max_gap(3)
        self.assertIsNotNone(t.gap_exceeded(now=now))

    def test_duplicate_flagged(self):
        t = SequenceTracker()
        _, dup1 = t.observe(5)
        _, dup2 = t.observe(5)
        self.assertFalse(dup1)
        self.assertTrue(dup2)


class TestSpamDetector(unittest.TestCase):
    def test_flood_over_threshold(self):
        d = SpamDetector(packets_per_sec=100)
        now = 1000.0
        verdict = None
        for _ in range(150):
            verdict = d.observe_rate("10.0.0.9", now=now)
        self.assertTrue(verdict.flooding)

    def test_identical_payload_repeats(self):
        d = SpamDetector(identical_payloads=20, repeat_window=5)
        now = 1000.0
        result = None
        for _ in range(25):
            result = d.observe_payload("10.0.0.9", "same-hash", now=now)
        self.assertIsNotNone(result)


class TestExfilDetector(unittest.TestCase):
    def test_volume_burst_to_external(self):
        d = ExfilDetector(trusted_cidrs=["10.0.0.0/8"], burst_bytes=1_000_000,
                          window_seconds=30)
        now = 1000.0
        event = None
        for _ in range(3):
            event = d.observe("10.0.0.1", "203.0.113.5", 500_000, "TCP", now=now)
        self.assertIsNotNone(event)
        self.assertEqual(event.kind, "volume")

    def test_internal_traffic_ignored(self):
        d = ExfilDetector(trusted_cidrs=["10.0.0.0/8"], burst_bytes=100)
        event = d.observe("10.0.0.1", "10.0.0.2", 10_000, "TCP")
        self.assertIsNone(event)

    def test_dns_tunnel_flagged(self):
        d = ExfilDetector(trusted_cidrs=["10.0.0.0/8"], dns_txt_len=100)
        event = d.observe("10.0.0.1", "8.8.8.8", 120, "UDP", dns_qname_len=150)
        self.assertIsNotNone(event)
        self.assertEqual(event.kind, "dns_tunnel")


if __name__ == "__main__":
    unittest.main()
