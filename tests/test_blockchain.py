"""Unit tests for the blockchain integrity ledger."""

import unittest

from src.blockchain.block import Block
from src.blockchain.chain import Blockchain
from src.blockchain.merkle import MerkleTree


class TestBlock(unittest.TestCase):
    def test_hash_is_deterministic(self):
        b1 = Block(1, "abc", "prev", timestamp=100.0, nonce=0)
        b2 = Block(1, "abc", "prev", timestamp=100.0, nonce=0)
        self.assertEqual(b1.compute_hash(), b2.compute_hash())

    def test_tamper_breaks_validity(self):
        b = Block(1, "abc", "prev", timestamp=100.0)
        self.assertTrue(b.is_valid())
        b.packet_hash = "xyz"              # tamper after the fact
        self.assertFalse(b.is_valid())

    def test_mining_meets_difficulty(self):
        b = Block(1, "abc", "prev", timestamp=100.0)
        b.mine(2)
        self.assertTrue(b.hash.startswith("00"))
        self.assertTrue(b.is_valid())


class TestMerkle(unittest.TestCase):
    def test_root_changes_with_leaves(self):
        t1 = MerkleTree(["a", "b", "c", "d"])
        t2 = MerkleTree(["a", "b", "c", "e"])
        self.assertNotEqual(t1.root, t2.root)

    def test_proof_verifies(self):
        leaves = ["a", "b", "c", "d", "e"]
        tree = MerkleTree(leaves)
        for i, leaf in enumerate(leaves):
            proof = tree.proof(i)
            self.assertTrue(MerkleTree.verify(leaf, i, proof, tree.root))

    def test_bad_proof_fails(self):
        tree = MerkleTree(["a", "b", "c", "d"])
        proof = tree.proof(0)
        self.assertFalse(MerkleTree.verify("WRONG", 0, proof, tree.root))


class TestBlockchain(unittest.TestCase):
    def setUp(self):
        self.chain = Blockchain(difficulty=1)

    def test_genesis_exists(self):
        self.assertEqual(len(self.chain), 1)
        self.assertEqual(self.chain.chain[0].packet_hash, "GENESIS")

    def test_anchor_and_verify_ok(self):
        self.chain.anchor(seq=1, packet_hash="hash-1")
        result = self.chain.verify_packet(1, "hash-1")
        self.assertTrue(result.ok)
        self.assertEqual(result.status, "verified")

    def test_tamper_detected(self):
        self.chain.anchor(seq=1, packet_hash="original")
        result = self.chain.verify_packet(1, "modified")
        self.assertEqual(result.status, "tampered")
        self.assertEqual(result.expected_hash, "original")

    def test_missing_anchor_is_unknown(self):
        result = self.chain.verify_packet(999, "whatever")
        self.assertEqual(result.status, "unknown")

    def test_replay_detection(self):
        self.chain.anchor(seq=1, packet_hash="dup")
        self.assertTrue(self.chain.is_replay("dup", seq=2))   # same hash, new seq
        self.assertFalse(self.chain.is_replay("dup", seq=1))  # same seq, not a replay

    def test_chain_links_and_validates(self):
        for i in range(5):
            self.chain.anchor(seq=i, packet_hash=f"h{i}")
        ok, msg = self.chain.is_valid()
        self.assertTrue(ok, msg)

    def test_tampering_a_block_invalidates_chain(self):
        for i in range(5):
            self.chain.anchor(seq=i, packet_hash=f"h{i}")
        self.chain.chain[2].packet_hash = "forged"   # rewrite history
        ok, _ = self.chain.is_valid()
        self.assertFalse(ok)

    def test_batch_anchoring(self):
        block = self.chain.anchor_batch([(1, "a"), (2, "b"), (3, "c")])
        self.assertTrue(block.merkle_root)
        self.assertTrue(self.chain.verify_packet(2, "b").ok)


if __name__ == "__main__":
    unittest.main()
