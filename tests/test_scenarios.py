"""Unit tests ensuring all SETU-NET simulation scenarios pass successfully."""

import unittest

from simulations.scenarios import (
    scenario_normal_multihop,
    scenario_sos_preemption,
    scenario_duplicate_suppression,
    scenario_ttl_expiration,
    scenario_tampered_signature,
    scenario_ack_roundtrip,
    scenario_sparse_network,
    scenario_clock_skew,
    scenario_scalability_50_nodes,
)
from src.engine import SetuNetEngine


class TestScenarios(unittest.TestCase):
    def test_scenario_normal_multihop(self):
        engine = SetuNetEngine()
        res = scenario_normal_multihop(engine)
        self.assertTrue(res.passed, f"Failed: {res.observed_metric}")

    def test_scenario_sos_preemption(self):
        engine = SetuNetEngine()
        res = scenario_sos_preemption(engine)
        self.assertTrue(res.passed, f"Failed: {res.observed_metric}")

    def test_scenario_duplicate_suppression(self):
        engine = SetuNetEngine()
        res = scenario_duplicate_suppression(engine)
        self.assertTrue(res.passed, f"Failed: {res.observed_metric}")

    def test_scenario_ttl_expiration(self):
        engine = SetuNetEngine()
        res = scenario_ttl_expiration(engine)
        self.assertTrue(res.passed, f"Failed: {res.observed_metric}")

    def test_scenario_tampered_signature(self):
        engine = SetuNetEngine()
        res = scenario_tampered_signature(engine)
        self.assertTrue(res.passed, f"Failed: {res.observed_metric}")

    def test_scenario_ack_roundtrip(self):
        engine = SetuNetEngine()
        res = scenario_ack_roundtrip(engine)
        self.assertTrue(res.passed, f"Failed: {res.observed_metric}")

    def test_scenario_sparse_network(self):
        engine = SetuNetEngine()
        res = scenario_sparse_network(engine)
        self.assertTrue(res.passed, f"Failed: {res.observed_metric}")

    def test_scenario_clock_skew(self):
        engine = SetuNetEngine()
        res = scenario_clock_skew(engine)
        self.assertTrue(res.passed, f"Failed: {res.observed_metric}")

    def test_scenario_scalability_50_nodes(self):
        engine = SetuNetEngine()
        res = scenario_scalability_50_nodes(engine)
        self.assertTrue(res.passed, f"Failed: {res.observed_metric}")


if __name__ == "__main__":
    unittest.main()
