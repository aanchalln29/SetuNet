"""Unit tests for SETU-NET PriorityMeshQueue and SOS preemption logic."""

import time
import unittest

from src.mesh.priority_queue import PriorityMeshQueue
from src.mesh.protocol import AlertCategory, AlertMessage, GPSLocation


def _make_alert(cat: AlertCategory, msg_id: str = "T1") -> AlertMessage:
    return AlertMessage(
        message_id=msg_id,
        category=cat,
        origin_node_id="phone-test",
        payload_text=f"Test alert for {cat.name}",
        location=GPSLocation(28.6, 77.2),
        timestamp=time.time(),
    )


class TestPriorityMeshQueue(unittest.TestCase):
    def test_priority_ordering(self):
        q = PriorityMeshQueue()
        gen = _make_alert(AlertCategory.GENERAL, "M-GEN")
        evac = _make_alert(AlertCategory.EVACUATION, "M-EVAC")
        troop = _make_alert(AlertCategory.TROOP_MOVEMENT, "M-TRP")
        sos = _make_alert(AlertCategory.SOS, "M-SOS")

        # Insert in reverse priority order
        q.put(gen)
        q.put(troop)
        q.put(evac)
        q.put(sos)

        # Extraction must be in strict priority order: SOS -> EVAC -> TROOP -> GENERAL
        self.assertEqual(q.get().category, AlertCategory.SOS)
        self.assertEqual(q.get().category, AlertCategory.EVACUATION)
        self.assertEqual(q.get().category, AlertCategory.TROOP_MOVEMENT)
        self.assertEqual(q.get().category, AlertCategory.GENERAL)
        self.assertTrue(q.is_empty())

    def test_sos_preemption_counter(self):
        q = PriorityMeshQueue()
        gen = _make_alert(AlertCategory.GENERAL, "M-GEN")
        q.put(gen)
        self.assertEqual(q.preemptions_count, 0)

        # SOS arriving behind General causes preemption
        sos = _make_alert(AlertCategory.SOS, "M-SOS")
        q.put(sos)
        self.assertEqual(q.preemptions_count, 1)

    def test_fifo_for_equal_priority(self):
        q = PriorityMeshQueue()
        sos1 = _make_alert(AlertCategory.SOS, "SOS-1")
        sos2 = _make_alert(AlertCategory.SOS, "SOS-2")
        q.put(sos1)
        q.put(sos2)

        self.assertEqual(q.get().message_id, "SOS-1")
        self.assertEqual(q.get().message_id, "SOS-2")

    def test_snapshot_representation(self):
        q = PriorityMeshQueue()
        q.put(_make_alert(AlertCategory.SOS, "SOS-1"))
        q.put(_make_alert(AlertCategory.GENERAL, "GEN-1"))
        
        snap = q.snapshot()
        self.assertEqual(len(snap), 2)
        self.assertEqual(snap[0]["category"], "SOS")
        self.assertEqual(snap[1]["category"], "GENERAL")


if __name__ == "__main__":
    unittest.main()
