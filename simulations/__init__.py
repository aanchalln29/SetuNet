"""SETU-NET Disaster Mesh Simulation Harness.

Exercises phone-to-phone multi-hop emergency alert forwarding, priority queues,
duplicate suppression, Ed25519 digital signatures, TTL limits, and reverse ACKs.
"""

from .scenarios import (
    ALL_SCENARIOS,
    scenario_ack_roundtrip,
    scenario_clock_skew,
    scenario_duplicate_suppression,
    scenario_normal_multihop,
    scenario_scalability_50_nodes,
    scenario_sos_preemption,
    scenario_sparse_network,
    scenario_tampered_signature,
    scenario_ttl_expiration,
)

__all__ = [
    "ALL_SCENARIOS",
    "scenario_normal_multihop",
    "scenario_sos_preemption",
    "scenario_duplicate_suppression",
    "scenario_ttl_expiration",
    "scenario_tampered_signature",
    "scenario_ack_roundtrip",
    "scenario_sparse_network",
    "scenario_clock_skew",
    "scenario_scalability_50_nodes",
]
