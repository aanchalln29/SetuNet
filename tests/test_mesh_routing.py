"""Unit tests for SETU-NET MeshRouter and Controlled Flooding."""

import unittest

from src.mesh.ack_manager import AckManager
from src.mesh.battery import BatteryMonitor
from src.mesh.mesh_router import MeshNode, MeshRouter, haversine_distance_meters
from src.mesh.protocol import AlertCategory
from src.mesh.storage import MeshDatabase


class TestMeshRouting(unittest.TestCase):
    def setUp(self):
        self.storage = MeshDatabase(":memory:")
        self.ack_mgr = AckManager()
        self.battery = BatteryMonitor()
        self.router = MeshRouter(self.storage, self.ack_mgr, self.battery)

        # Register 3 nodes in range: A -> B -> C (~120m apart)
        self.node_a = MeshNode("phone-A", "Phone A", "sender", 28.6139, 77.2090)
        self.node_b = MeshNode("phone-B", "Phone B", "relay", 28.6150, 77.2090)  # ~122m from A
        self.node_c = MeshNode("phone-C", "Phone C", "relay", 28.6161, 77.2090)  # ~122m from B
        # Far away node D (~3500m away)
        self.node_d = MeshNode("phone-D", "Phone D", "control", 28.6450, 77.2090)

        for n in [self.node_a, self.node_b, self.node_c, self.node_d]:
            self.router.add_node(n)

    def test_neighbor_discovery_within_range(self):
        # A should have B as neighbor, but not C or D (C is ~244m away from A)
        a_neighbors = self.router.get_neighbors("phone-A")
        self.assertIn("phone-B", a_neighbors)
        self.assertNotIn("phone-D", a_neighbors)

        # B should have both A and C as neighbors
        b_neighbors = self.router.get_neighbors("phone-B")
        self.assertIn("phone-A", b_neighbors)
        self.assertIn("phone-C", b_neighbors)

    def test_multi_hop_controlled_flooding(self):
        alert = self.router.broadcast_alert(
            sender_id="phone-A",
            category=AlertCategory.SOS,
            payload_text="Multi-hop test alert",
            initial_ttl=6,
        )
        # Alert should reach Phone B and Phone C
        acks = self.ack_mgr.get_acks(alert.message_id)
        ack_nodes = {a["ack_node_id"] for a in acks}
        self.assertIn("phone-B", ack_nodes)
        self.assertIn("phone-C", ack_nodes)
        self.assertNotIn("phone-D", ack_nodes)  # D is out of range

    def test_ttl_countdown_limit(self):
        # With initial_ttl = 1, Phone B receives it, but TTL drops to 0 and stops without forwarding to C
        alert = self.router.broadcast_alert(
            sender_id="phone-A",
            category=AlertCategory.GENERAL,
            payload_text="Low TTL alert",
            initial_ttl=1,
        )
        acks = self.ack_mgr.get_acks(alert.message_id)
        ack_nodes = {a["ack_node_id"] for a in acks}
        self.assertIn("phone-B", ack_nodes)
        self.assertNotIn("phone-C", ack_nodes)  # C didn't get it because TTL expired!
        self.assertGreaterEqual(self.router.ttl_dropped_count, 1)


if __name__ == "__main__":
    unittest.main()
