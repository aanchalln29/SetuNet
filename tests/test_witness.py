"""Unit tests for Merkle batching, the witness quorum, and proof export."""

import unittest

from src.blockchain.chain import Blockchain
from src.blockchain.witness import WitnessQuorum


class TestMerkleBatching(unittest.TestCase):
    def test_batching_seals_fewer_blocks(self):
        chain = Blockchain(difficulty=1, batch_size=8)
        for i in range(16):
            chain.anchor(i, f"h{i}")
        # 16 packets / 8 per batch = 2 sealed blocks + genesis.
        self.assertEqual(len(chain), 3)

    def test_verify_works_before_seal(self):
        chain = Blockchain(difficulty=1, batch_size=8)
        chain.anchor(0, "h0")                 # buffered, not yet sealed
        self.assertTrue(chain.verify_packet(0, "h0").ok)

    def test_merkle_proof_roundtrip(self):
        chain = Blockchain(difficulty=1, batch_size=8)
        for i in range(10):
            chain.anchor(i, f"hash-{i}")
        proof = chain.merkle_proof(3)
        self.assertIsNotNone(proof)
        self.assertTrue(Blockchain.verify_merkle_proof(
            proof["leaf_hash"], proof["proof"], proof["merkle_root"],
            proof["leaf_index"]))

    def test_batched_chain_validates(self):
        chain = Blockchain(difficulty=1, batch_size=5)
        for i in range(12):
            chain.anchor(i, f"h{i}")
        chain.flush()
        self.assertTrue(chain.is_valid()[0])


class TestWitnessQuorum(unittest.TestCase):
    def setUp(self):
        self.q = WitnessQuorum(difficulty=1, batch_size=4, nodes=3)
        for i in range(12):
            self.q.anchor(i, f"hash-{i}")

    def test_all_witnesses_agree_when_clean(self):
        vote = self.q.vote(5, "hash-5")
        self.assertEqual(vote.status, "verified")
        self.assertEqual(vote.agree, 3)
        self.assertTrue(vote.confirmed)

    def test_one_compromised_node_is_outvoted(self):
        self.q.tamper_witness(2, 5, "FORGED")
        vote = self.q.vote(5, "hash-5")
        self.assertEqual(vote.status, "verified")      # majority still correct
        self.assertEqual(vote.agree, 2)                # 2 of 3
        self.assertTrue(vote.confirmed)
        self.assertEqual(vote.compromised, ["W3"])

    def test_quorum_still_valid_with_one_bad_node(self):
        self.q.tamper_witness(2, 5, "FORGED")
        ok, msg = self.q.is_valid()
        self.assertTrue(ok)                            # 2/3 intact => quorum holds
        self.assertIn("W3", msg)

    def test_quorum_breaks_when_majority_compromised(self):
        self.q.tamper_witness(0, 5, "FORGED1")
        self.q.tamper_witness(1, 5, "FORGED2")
        ok, _ = self.q.is_valid()
        self.assertFalse(ok)                           # only 1/3 intact

    def test_tampered_packet_detected_by_quorum(self):
        result = self.q.verify_packet(5, "WRONG-HASH")
        self.assertEqual(result.status, "tampered")    # all agree it's wrong


if __name__ == "__main__":
    unittest.main()
