"""Unit tests for SQLite MeshDatabase persistence."""

import unittest

from src.mesh.protocol import AckMessage, AlertCategory, AlertMessage, GPSLocation
from src.mesh.storage import MeshDatabase


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.db = MeshDatabase(":memory:")

    def tearDown(self):
        self.db.close()

    def test_save_and_retrieve_alert(self):
        alert = AlertMessage(
            message_id="SETU-DB-001",
            category=AlertCategory.SOS,
            origin_node_id="phone-1",
            payload_text="SQLite storage test",
            location=GPSLocation(28.6139, 77.2090),
            ttl=6,
            hop_count=1,
            hop_path=["phone-1", "phone-2"],
        )
        self.db.save_alert(alert, status="DELIVERED")
        alerts = self.db.get_recent_alerts(limit=5)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["message_id"], "SETU-DB-001")
        self.assertEqual(alerts[0]["category"], "SOS")
        self.assertEqual(alerts[0]["hop_path"], ["phone-1", "phone-2"])

    def test_save_and_retrieve_ack(self):
        ack = AckMessage(
            ack_id="ACK-123",
            original_message_id="SETU-DB-001",
            alert_category=AlertCategory.SOS,
            ack_node_id="phone-2",
            origin_node_id="phone-1",
            hops_to_node=1,
            received_timestamp=1000.0,
            latency_ms=650.0,
            return_path=["phone-2", "phone-1"],
            status="DELIVERED",
        )
        self.db.save_ack(ack)
        acks = self.db.get_acks_for_message("SETU-DB-001")
        self.assertEqual(len(acks), 1)
        self.assertEqual(acks[0]["ack_id"], "ACK-123")
        self.assertEqual(acks[0]["latency_ms"], 650.0)


if __name__ == "__main__":
    unittest.main()
