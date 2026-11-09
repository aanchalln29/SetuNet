"""Blockchain — the append-only ledger of packet fingerprints.

Two roles use this one structure:

* **Sender side** calls :meth:`anchor` as it transmits each packet, committing
  the packet's hash to the chain *before* it goes on the wire.
* **Receiver side** calls :meth:`verify_packet`, re-hashing what actually arrived
  and comparing against the anchored value. A mismatch means tampering; a missing
  sequence number means loss/theft.

The chain also detects **replay attacks**: the same payload hash anchored twice
with different timestamps is a re-transmitted packet.

**Merkle batching.** Sealing one block per packet is wasteful. With
``batch_size > 1`` the chain accumulates packet hashes and seals them into a
single block under one **Merkle root** (so one block witnesses many packets).
The per-packet hash is recorded the instant it is anchored, so verification stays
an O(1) lookup — well under a microsecond — regardless of batching. Every packet
can still be *proved* to belong to its block via a Merkle audit path
(:meth:`merkle_proof`), which is what the incident proof-export builds on.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Any, Optional

from .block import Block
from .merkle import MerkleTree


@dataclass
class VerificationResult:
    seq: int
    status: str            # "verified" | "tampered" | "missing" | "unknown"
    expected_hash: Optional[str]
    actual_hash: Optional[str]
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "verified"


class Blockchain:
    """A lightweight, thread-safe, proof-of-work chain of packet hashes.

    ``batch_size`` controls Merkle batching: 1 seals a block per packet (simple,
    the default); N accumulates N packets per Merkle-batched block.
    """

    def __init__(self, difficulty: int = 2, sender_id: str = "node-A",
                 batch_size: int = 1):
        self.difficulty = difficulty
        self.sender_id = sender_id
        self.batch_size = max(1, int(batch_size))
        self._lock = threading.RLock()
        self.chain: list[Block] = [self._genesis()]
        # seq -> anchored packet hash, for O(1) receiver verification.
        self._anchored: dict[int, str] = {}
        # payload_hash -> first seq that used it, for replay detection.
        self._seen_hashes: dict[str, int] = {}
        # Pending (seq, hash) not yet sealed into a block.
        self._pending: list[tuple[int, str]] = []
        # seq -> {block_index, leaf_index} once sealed (for Merkle proofs).
        self._anchor_meta: dict[int, dict[str, int]] = {}
        # block_index -> ordered leaf hashes (to regenerate proofs/roots).
        self._block_leaves: dict[int, list[str]] = {}

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def _genesis(self) -> Block:
        g = Block(index=0, packet_hash="GENESIS", prev_hash="0" * 64, seq=-1,
                  sender_id=self.sender_id)
        g.mine(self.difficulty)
        return g

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def __len__(self) -> int:
        return len(self.chain)

    # ------------------------------------------------------------------ #
    # Sender side — anchoring
    # ------------------------------------------------------------------ #
    def anchor(self, seq: int, packet_hash: str) -> Optional[Block]:
        """Anchor one packet hash. Returns the sealed block, or None if the
        packet is still buffered in an unsealed batch."""
        with self._lock:
            self._anchored[seq] = packet_hash
            self._seen_hashes.setdefault(packet_hash, seq)
            self._pending.append((seq, packet_hash))
            if len(self._pending) >= self.batch_size:
                return self._seal_batch()
            return None

    def anchor_batch(self, items: list[tuple[int, str]]) -> Block:
        """Anchor a batch of (seq, packet_hash) under a single Merkle root now."""
        with self._lock:
            for seq, h in items:
                self._anchored[seq] = h
                self._seen_hashes.setdefault(h, seq)
            self._pending.extend(items)
            block = self._seal_batch()
            assert block is not None
            return block

    def flush(self) -> Optional[Block]:
        """Seal any buffered packets into a block immediately."""
        with self._lock:
            return self._seal_batch() if self._pending else None

    def _seal_batch(self) -> Optional[Block]:
        """Internal: seal the pending buffer into one Merkle-rooted block."""
        if not self._pending:
            return None
        items = self._pending
        leaves = [h for _, h in items]
        tree = MerkleTree(leaves)
        block = Block(
            index=len(self.chain),
            packet_hash=tree.root,
            prev_hash=self.last_block.hash,
            seq=items[0][0],
            sender_id=self.sender_id,
            merkle_root=tree.root,
        )
        block.mine(self.difficulty)
        self.chain.append(block)
        self._block_leaves[block.index] = leaves
        for leaf_index, (seq, _h) in enumerate(items):
            self._anchor_meta[seq] = {"block_index": block.index,
                                      "leaf_index": leaf_index}
        self._pending = []
        return block

    # ------------------------------------------------------------------ #
    # Receiver side — verification
    # ------------------------------------------------------------------ #
    def verify_packet(self, seq: int, actual_hash: str) -> VerificationResult:
        """Compare an arrived packet against what the sender anchored (O(1))."""
        with self._lock:
            expected = self._anchored.get(seq)
        if expected is None:
            return VerificationResult(seq, "unknown", None, actual_hash,
                                      "No anchor on chain for this sequence number")
        if expected == actual_hash:
            return VerificationResult(seq, "verified", expected, actual_hash,
                                      "Hash matches the blockchain anchor")
        return VerificationResult(seq, "tampered", expected, actual_hash,
                                   "Received hash differs from blockchain anchor")

    def is_replay(self, packet_hash: str, seq: int) -> bool:
        """True if this exact payload hash was already anchored under a *different* seq."""
        with self._lock:
            first = self._seen_hashes.get(packet_hash)
            return first is not None and first != seq

    # ------------------------------------------------------------------ #
    # Merkle proof (the basis of incident proof-export)
    # ------------------------------------------------------------------ #
    def merkle_proof(self, seq: int) -> Optional[dict[str, Any]]:
        """Return a Merkle audit path proving ``seq``'s hash is in its block.

        Flushes any pending batch first so a just-anchored packet is provable.
        """
        with self._lock:
            if seq not in self._anchor_meta:
                self._seal_batch()  # seal so a buffered packet becomes provable
            meta = self._anchor_meta.get(seq)
            if meta is None:
                return None
            block = self.chain[meta["block_index"]]
            leaves = self._block_leaves[meta["block_index"]]
            tree = MerkleTree(leaves)
            proof = tree.proof(meta["leaf_index"])
            return {
                "seq": seq,
                "leaf_hash": self._anchored.get(seq),
                "leaf_index": meta["leaf_index"],
                "proof": proof,
                "merkle_root": tree.root,
                "block_index": block.index,
                "block_hash": block.hash,
                "prev_hash": block.prev_hash,
                "timestamp": block.timestamp,
                "batch_size": len(leaves),
            }

    @staticmethod
    def verify_merkle_proof(leaf_hash: str, proof: list, root: str,
                            leaf_index: int) -> bool:
        """Independently re-check a Merkle proof (used by auditors)."""
        tuples = [(p[0], p[1]) for p in proof]
        return MerkleTree.verify(leaf_hash, leaf_index, tuples, root)

    # ------------------------------------------------------------------ #
    # Integrity of the ledger itself
    # ------------------------------------------------------------------ #
    def is_valid(self) -> tuple[bool, str]:
        """Validate the whole chain: per-block hashes, links, PoW, Merkle roots."""
        with self._lock:
            target = "0" * self.difficulty
            for i, block in enumerate(self.chain):
                if not block.is_valid():
                    return False, f"Block #{i} content/hash mismatch (tampered)"
                if i > 0 and block.prev_hash != self.chain[i - 1].hash:
                    return False, f"Block #{i} broken link to #{i - 1}"
                if i > 0 and not block.hash.startswith(target):
                    return False, f"Block #{i} fails proof-of-work target"
                leaves = self._block_leaves.get(i)
                if leaves is not None and MerkleTree(leaves).root != block.merkle_root:
                    return False, f"Block #{i} Merkle root does not match its packets"
            return True, "Chain intact"

    # ------------------------------------------------------------------ #
    # Views / persistence
    # ------------------------------------------------------------------ #
    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            out = []
            for b in self.chain[-n:]:
                d = b.to_dict()
                d["packet_count"] = len(self._block_leaves.get(b.index, []))
                out.append(d)
            return out

    def to_json(self) -> str:
        with self._lock:
            return json.dumps([b.to_dict() for b in self.chain], indent=2)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())
