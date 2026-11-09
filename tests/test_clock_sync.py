"""Unit tests for ClockSyncEstimator and time difference estimation."""

import unittest

from src.mesh.clock_sync import ClockSyncEstimator


class TestClockSync(unittest.TestCase):
    def test_pairwise_time_offset_calculation(self):
        est = ClockSyncEstimator("node-A")
        # Node B's clock is 2.0s ahead of Node A
        t0 = 100.0   # A sends at 100.0
        t1 = 102.02  # B receives at 102.02 (20ms transmission + 2s clock skew)
        t2 = 102.03  # B replies at 102.03 (10ms turnaround)
        t3 = 100.05  # A receives reply at 100.05

        record = est.record_exchange("node-B", t0, t1, t2, t3)
        self.assertAlmostEqual(record.estimated_offset_seconds, 2.0, delta=0.01)
        self.assertAlmostEqual(record.round_trip_delay_ms, 40.0, delta=1.0)

    def test_timestamp_normalization(self):
        est = ClockSyncEstimator("node-A")
        est.record_exchange("node-B", 100.0, 105.02, 105.03, 100.05)  # 5s skew
        normalized = est.normalize_timestamp(1005.0, "node-B")
        self.assertAlmostEqual(normalized, 1000.0, delta=0.05)


if __name__ == "__main__":
    unittest.main()
