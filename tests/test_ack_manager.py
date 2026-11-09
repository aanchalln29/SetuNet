"""Unit tests for AckManager, reverse hop traces, and delivery reports."""

import unittest

from src.mesh.ack_manager import AckManager
from src.mesh.protocol import AlertCategory, AlertMessage, GPSLocation


class TestAckManager(unittest.TestCase):
    def test_ack_creation_and_return_path(self):
        mgr = AckManager()
        alert = AlertMessage(
            message_id="SETU-ACK-001",
            category=AlertCategory.EVACUATION,
            origin_node_id="phone-1",
            payload_text="Evacuate now",
            location=GPSLocation(28.6, 77.2),
            hop_count=2,
            hop_path=["phone-1", "phone-2", "phone-3"],
        )

        ack = mgr.create_ack(alert, receiving_node_id="phone-3", simulated_per_hop_latency_ms=500.0)
        self.assertEqual(ack.original_message_id, "SETU-ACK-001")
        self.assertEqual(ack.hops_to_node, 2)
        # Return path should be reverse: phone-3 -> phone-2 -> phone-1
        self.assertEqual(ack.return_path, ["phone-3", "phone-2", "phone-1"])

    def test_delivery_report_metrics(self):
        mgr = AckManager()
        alert = AlertMessage(
            message_id="SETU-REP-001",
            category=AlertCategory.SOS,
            origin_node_id="phone-1",
            payload_text="Report test",
            location=GPSLocation(28.6, 77.2),
        )

        ack1 = mgr.create_ack(alert, "phone-2", simulated_per_hop_latency_ms=600.0)
        ack2 = mgr.create_ack(alert, "phone-3", simulated_per_hop_latency_ms=650.0)
        mgr.record_ack(ack1)
        mgr.record_ack(ack2)

        report = mgr.generate_delivery_report(alert, total_reachable_nodes=2)
        self.assertEqual(report.acknowledged_nodes_count, 2)
        self.assertEqual(report.delivery_ratio_pct, 100.0)
        self.assertTrue(report.to_dict()["target_delivery_met"])


if __name__ == "__main__":
    unittest.main()
