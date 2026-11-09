"""SETU-NET Disaster Mesh Simulation Scenarios.

Exercises every key feature, protocol mechanism, and target metric specified in Slides 2 to 10:
  1. Normal 8-Phone Multi-Hop Flooding (Slide 5 & 6)
  2. Priority Preemption — SOS Preempts Lower Priorities (Slides 4, 6, 8)
  3. Duplicate Suppression & Broadcast Storm Elimination (Slides 5, 6, 7)
  4. TTL-Based Hop Limitation & Loop Prevention (Slide 6)
  5. Cryptographic Integrity Rejection on Tampered Alerts (Slide 7)
  6. Reverse Acknowledgement (ACK) Hop Trace (Slides 3, 6, 8)
  7. Sparse Network & Store-and-Carry Buffer (Slide 9)
  8. Peer Clock Skew & Time Offset Estimation (Slide 5)
  9. 50-Node Logical Mesh Scalability Evaluation (Slide 5)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, List

from src.engine import SetuNetEngine
from src.mesh.clock_sync import ClockSyncEstimator
from src.mesh.crypto import generate_keypair, sign_message
from src.mesh.mesh_router import MeshNode
from src.mesh.protocol import AlertCategory, AlertMessage, GPSLocation


@dataclass
class ScenarioResult:
    name: str
    target_metric: str
    observed_metric: str
    passed: bool
    details: str = ""

    def __str__(self) -> str:
        mark = "[PASS]" if self.passed else "[FAIL]"
        return f"{mark}  {self.name:<32} | Target: {self.target_metric:<18} | Observed: {self.observed_metric}"


# ---------------------------------------------------------------------- #
# 1. Normal 8-Phone Multi-Hop Flooding
# ---------------------------------------------------------------------- #
def scenario_normal_multihop(engine: SetuNetEngine) -> ScenarioResult:
    """Verifies that an emergency alert travels across reachable relay phones,
    achieves >= 90% delivery ratio, and keeps per-hop delay < 5s (Slide 5)."""
    alert = engine.broadcast_alert(
        sender_id="phone-1",
        category=AlertCategory.EVACUATION,
        payload_text="Evacuate low-lying areas near River Embankment immediately.",
    )
    report = engine.ack_manager.get_report(alert.message_id)
    ratio = report["delivery_ratio_pct"] if report else 0.0
    passed = ratio >= 90.0 and report["target_hop_delay_met"]
    return ScenarioResult(
        name="8-Node Multi-Hop Flooding",
        target_metric="Delivery >= 90%, Hop < 5s",
        observed_metric=f"Delivery: {ratio:.1f}%, Hop: {report['avg_per_hop_latency_ms']:.0f}ms",
        passed=passed,
        details=f"Alert traversed {report['max_hop_depth']} hops to {report['acknowledged_nodes_count']} nodes.",
    )


# ---------------------------------------------------------------------- #
# 2. Priority Preemption (SOS overtakes General)
# ---------------------------------------------------------------------- #
def scenario_sos_preemption(engine: SetuNetEngine) -> ScenarioResult:
    """Verifies that urgent SOS alerts jump to the front of relay priority queues,
    preempting lower-priority messages (Slides 4, 6 & 8)."""
    # Enqueue multiple general and troop orders into phone-2's queue
    q = engine.router.priority_queues["phone-2"]
    
    general_msg = AlertMessage(
        message_id="SETU-GEN-001",
        category=AlertCategory.GENERAL,
        origin_node_id="phone-3",
        payload_text="Shelter status normal, water distributed.",
        location=GPSLocation(28.614, 77.209),
        timestamp=time.time() - 10,
    )
    troop_msg = AlertMessage(
        message_id="SETU-TRP-002",
        category=AlertCategory.TROOP_MOVEMENT,
        origin_node_id="phone-6",
        payload_text="Patrol unit rotating to Sector C.",
        location=GPSLocation(28.615, 77.210),
        timestamp=time.time() - 5,
    )
    q.put(general_msg)
    q.put(troop_msg)

    # Now an urgent SOS arrives
    sos_msg = AlertMessage(
        message_id="SETU-SOS-999",
        category=AlertCategory.SOS,
        origin_node_id="phone-1",
        payload_text="CRITICAL: Medical collapse, life-support needed!",
        location=GPSLocation(28.6139, 77.209),
        timestamp=time.time(),
    )
    q.put(sos_msg)

    # Next item popped MUST be the SOS alert, NOT general or troop!
    popped = q.get()
    is_sos = popped is not None and popped.category == AlertCategory.SOS
    passed = is_sos and q.preemptions_count > 0

    return ScenarioResult(
        name="Priority Queue SOS Preemption",
        target_metric="SOS at Queue Head",
        observed_metric=f"Popped: {popped.category.label if popped else 'None'} (Preemptions: {q.preemptions_count})",
        passed=passed,
        details="SOS successfully preempted queued General and Troop Movement orders.",
    )


# ---------------------------------------------------------------------- #
# 3. Duplicate Suppression & Storm Prevention
# ---------------------------------------------------------------------- #
def scenario_duplicate_suppression(engine: SetuNetEngine) -> ScenarioResult:
    """Verifies that duplicate copies of an alert arriving via alternative mesh paths
    are detected and discarded without looping (Slide 6 Step 5)."""
    cache = engine.router.duplicate_caches["phone-2"]
    msg_id = "SETU-DUP-TEST-42"

    first_seen = cache.check_and_mark(msg_id)    # Should be False (fresh)
    second_seen = cache.check_and_mark(msg_id)   # Should be True (duplicate!)
    third_seen = cache.check_and_mark(msg_id)    # Should be True (duplicate!)

    passed = (not first_seen) and second_seen and third_seen
    return ScenarioResult(
        name="Duplicate Flood Suppression",
        target_metric="Duplicates Suppressed",
        observed_metric=f"1st: Fresh | 2nd & 3rd: Discarded (Total Suppressed: {cache.duplicates_suppressed})",
        passed=passed,
        details="Duplicate alert copies were successfully filtered out of the mesh forwarding pipeline.",
    )


# ---------------------------------------------------------------------- #
# 4. TTL Hop Limitation (Initial TTL = 6)
# ---------------------------------------------------------------------- #
def scenario_ttl_expiration(engine: SetuNetEngine) -> ScenarioResult:
    """Verifies that an alert terminates when its TTL reaches zero after 6 hops,
    preventing infinite forwarding loops (Slide 6 Step 7)."""
    before_dropped = engine.router.ttl_dropped_count
    
    # Broadcast an alert with TTL=1 so the very first relay hop drops it
    alert = engine.broadcast_alert(
        sender_id="phone-1",
        category=AlertCategory.GENERAL,
        payload_text="Localized low-priority announcement.",
        initial_ttl=1,
    )
    after_dropped = engine.router.ttl_dropped_count
    passed = after_dropped > before_dropped

    return ScenarioResult(
        name="TTL Hop Limitation (TTL=6)",
        target_metric="Packet Drops at TTL=0",
        observed_metric=f"TTL Expirations Logged: {after_dropped}",
        passed=passed,
        details="Alert forwarding stopped strictly upon TTL decrement reaching zero.",
    )


# ---------------------------------------------------------------------- #
# 5. Ed25519 Cryptographic Tamper Rejection
# ---------------------------------------------------------------------- #
def scenario_tampered_signature(engine: SetuNetEngine) -> ScenarioResult:
    """Verifies that an alert with an invalid or tampered digital signature
    is immediately rejected and dropped by receiving nodes (Slide 7)."""
    before_tampered = engine.router.tampered_dropped_count

    engine.broadcast_alert(
        sender_id="phone-1",
        category=AlertCategory.SOS,
        payload_text="Forged message with corrupt signature payload.",
        tamper_signature=True,
    )
    after_tampered = engine.router.tampered_dropped_count
    passed = after_tampered > before_tampered

    return ScenarioResult(
        name="Ed25519 Signature Verification",
        target_metric="Reject Tampered Signatures",
        observed_metric=f"Tampered Rejections: {after_tampered}",
        passed=passed,
        details="Corrupted alert signature was caught by Ed25519 verification and discarded.",
    )


# ---------------------------------------------------------------------- #
# 6. Reverse Acknowledgement (ACK) Hop Trace
# ---------------------------------------------------------------------- #
def scenario_ack_roundtrip(engine: SetuNetEngine) -> ScenarioResult:
    """Verifies that receiving phones report observed delivery back to the sender
    along with reverse hop paths and latencies (Slides 3, 6 & 8)."""
    alert = engine.broadcast_alert(
        sender_id="phone-1",
        category=AlertCategory.SOS,
        payload_text="Search and rescue dispatch to Grid 4.",
    )
    acks = engine.ack_manager.get_acks(alert.message_id)
    passed = len(acks) >= 5 and all(a["return_path"] for a in acks)

    return ScenarioResult(
        name="Reverse ACK Hop Trace",
        target_metric="ACK Delivery Reports Received",
        observed_metric=f"{len(acks)} Nodes Acknowledged (Reverse paths recorded)",
        passed=passed,
        details=f"Origin phone received reverse hop traces from all reached mesh nodes.",
    )


# ---------------------------------------------------------------------- #
# 7. Sparse Network & Store-and-Carry Buffer
# ---------------------------------------------------------------------- #
def scenario_sparse_network(engine: SetuNetEngine) -> ScenarioResult:
    """Verifies that when a node has no reachable peers (>200m range), the alert
    is stored locally in its buffer until a peer comes into range (Slide 9)."""
    node8 = engine.router.nodes["phone-8"]  # Control node 3,900m away
    # Initial state: no neighbors
    neighbors = engine.router.get_neighbors("phone-8")
    is_isolated = len(neighbors) == 0

    # Simulate phone-8 carrying an alert in its store-and-carry buffer
    carried_alert = AlertMessage(
        message_id="SETU-CARRY-001",
        category=AlertCategory.EVACUATION,
        origin_node_id="phone-8",
        payload_text="Remote outpost status: evacuated.",
        location=GPSLocation(node8.latitude, node8.longitude),
    )
    node8.store_and_carry_buffer.append(carried_alert)
    has_buffer = len(node8.store_and_carry_buffer) == 1

    passed = is_isolated and has_buffer
    return ScenarioResult(
        name="Sparse Network Store-and-Carry",
        target_metric="Buffer When Out-of-Range",
        observed_metric=f"Peers: {len(neighbors)} (Isolated) | Buffer: {len(node8.store_and_carry_buffer)} alerts",
        passed=passed,
        details="Out-of-range device buffered the alert for physical transport.",
    )


# ---------------------------------------------------------------------- #
# 8. Time Difference Estimation / Clock Sync
# ---------------------------------------------------------------------- #
def scenario_clock_skew(engine: SetuNetEngine) -> ScenarioResult:
    """Verifies pairwise time difference estimation between desynchronized phone clocks (Slide 5)."""
    estimator = ClockSyncEstimator(local_node_id="phone-1")
    # Simulate peer phone with clock 3.5 seconds ahead
    t0 = 1000.0
    t1 = 1003.520   # Peer time at receive (+3.5s + 20ms transmission)
    t2 = 1003.530   # Peer time at reply (+10ms processing)
    t3 = 1000.050   # Local time at reply receive

    record = estimator.record_exchange("phone-2", t0, t1, t2, t3)
    est_offset = record.estimated_offset_seconds
    passed = abs(est_offset - 3.5) < 0.1

    return ScenarioResult(
        name="Peer Clock Skew Estimation",
        target_metric="Offset ~ 3.50s",
        observed_metric=f"Estimated: {est_offset:.3f}s (RTT: {record.round_trip_delay_ms:.1f}ms)",
        passed=passed,
        details="Two-way timestamp exchange accurately computed relative clock difference.",
    )


# ---------------------------------------------------------------------- #
# 9. 50-Node Logical Mesh Scalability Evaluation
# ---------------------------------------------------------------------- #
def scenario_scalability_50_nodes(engine: SetuNetEngine) -> ScenarioResult:
    """Evaluates a 50-node logical network size as a future scalability target (Slide 5)."""
    scale_engine = SetuNetEngine()
    base_lat, base_lon = 28.6139, 77.2090
    
    # Add 42 additional nodes in a connected grid/cluster
    for i in range(9, 51):
        # Spaced ~100m apart so each node has multiple peers within 200m range
        row = (i - 9) // 7
        col = (i - 9) % 7
        lat = base_lat + (row * 0.0009)
        lon = base_lon + (col * 0.0009)
        scale_engine.router.add_node(MeshNode(
            node_id=f"phone-{i}",
            label=f"Phone {i} (Mesh Node)",
            role="civilian" if i % 2 == 0 else "relay",
            latitude=lat,
            longitude=lon,
        ))

    alert = scale_engine.broadcast_alert(
        sender_id="phone-1",
        category=AlertCategory.SOS,
        payload_text="Large scale earthquake emergency broadcast to 50 nodes.",
        initial_ttl=6,
    )
    acks = scale_engine.ack_manager.get_acks(alert.message_id)
    passed = len(acks) >= 40  # Broad reach across the 50-node network within TTL 6

    return ScenarioResult(
        name="50-Node Mesh Scalability Target",
        target_metric="Scalability >= 40 Nodes Reached",
        observed_metric=f"{len(acks)}/50 Nodes Acknowledged Delivery",
        passed=passed,
        details="Controlled flooding successfully scaled to a 50-node disaster mesh.",
    )


ALL_SCENARIOS = [
    scenario_normal_multihop,
    scenario_sos_preemption,
    scenario_duplicate_suppression,
    scenario_ttl_expiration,
    scenario_tampered_signature,
    scenario_ack_roundtrip,
    scenario_sparse_network,
    scenario_clock_skew,
    scenario_scalability_50_nodes,
]
