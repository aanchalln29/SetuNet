"""WitnessQuorum — replicate the ledger across N independent witness nodes.

A single ledger is a single point of compromise: an attacker who rewrites the
one store can forge history. PacketGuard therefore anchors every packet on **three
independent witness chains** and accepts a fact only when a **2-of-3 majority**
agrees. Compromising one witness is not enough — the other two outvote it, and the
quorum flags the disagreeing node as tampered.

This class duck-types :class:`Blockchain` (same ``anchor`` / ``verify_packet`` /
``is_replay`` / ``is_valid`` / ``recent`` / ``__len__`` / ``merkle_proof`` surface),
so :class:`~src.engine.PacketGuardEngine` can use a single chain or a quorum
interchangeably.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from .block import Block
from .chain import Blockchain, VerificationResult


@dataclass
class QuorumVote:
    status: str                      # "verified" | "tampered" | "unknown"
    agree: int                       # how many witnesses returned the majority status
    total: int
    per_witness: dict[str, str] = field(default_factory=dict)
    compromised: list[str] = field(default_factory=list)

    @property
    def confirmed(self) -> bool:
        return self.agree >= (self.total // 2 + 1)


class WitnessQuorum:
    def __init__(self, difficulty: int = 2, sender_id: str = "node",
                 batch_size: int = 1, nodes: int = 3):
        if nodes < 3 or nodes % 2 == 0:
            # Need an odd number >= 3 for a meaningful majority.
            nodes = 3
        self.nodes = nodes
        self.threshold = nodes // 2 + 1          # 2 of 3
        self._lock = threading.RLock()
        self.witnesses: list[Blockchain] = [
            Blockchain(difficulty=difficulty, sender_id=f"{sender_id}-W{i+1}",
                       batch_size=batch_size)
            for i in range(nodes)
        ]
        self._names = [f"W{i+1}" for i in range(nodes)]

    # ------------------------------------------------------------------ #
    # Blockchain-compatible surface (the "primary" is witness 0 for reads;
    # replicas are identical, so any witness answers reads equivalently).
    # ------------------------------------------------------------------ #
    @property
    def _primary(self) -> Blockchain:
        return self.witnesses[0]

    @property
    def difficulty(self) -> int:
        return self._primary.difficulty

    @property
    def chain(self) -> list[Block]:
        return self._primary.chain

    def __len__(self) -> int:
        return len(self._primary)

    def anchor(self, seq: int, packet_hash: str) -> Optional[Block]:
        with self._lock:
            block = None
            for w in self.witnesses:
                block = w.anchor(seq, packet_hash)
            return block            # all replicas seal identically

    def anchor_batch(self, items: list[tuple[int, str]]) -> Block:
        with self._lock:
            block = None
            for w in self.witnesses:
                block = w.anchor_batch(items)
            return block            # type: ignore[return-value]

    def flush(self) -> Optional[Block]:
        with self._lock:
            block = None
            for w in self.witnesses:
                block = w.flush()
            return block

    def is_replay(self, packet_hash: str, seq: int) -> bool:
        return self._primary.is_replay(packet_hash, seq)

    # ------------------------------------------------------------------ #
    # Quorum verification
    # ------------------------------------------------------------------ #
    def vote(self, seq: int, actual_hash: str) -> QuorumVote:
        """Collect each witness's verdict and resolve by majority."""
        per: dict[str, str] = {}
        for name, w in zip(self._names, self.witnesses):
            per[name] = w.verify_packet(seq, actual_hash).status
        tally: dict[str, int] = {}
        for status in per.values():
            tally[status] = tally.get(status, 0) + 1
        majority_status = max(tally, key=tally.get)
        agree = tally[majority_status]
        compromised = [n for n, s in per.items() if s != majority_status]
        return QuorumVote(status=majority_status, agree=agree, total=self.nodes,
                          per_witness=per, compromised=compromised)

    def verify_packet(self, seq: int, actual_hash: str) -> VerificationResult:
        """Blockchain-compatible verify, resolved by 2-of-3 majority."""
        vote = self.vote(seq, actual_hash)
        base = self._primary.verify_packet(seq, actual_hash)
        detail = (f"quorum {vote.agree}/{vote.total} agree ({vote.status})")
        if vote.compromised:
            detail += f"; disagreeing witnesses flagged: {', '.join(vote.compromised)}"
        return VerificationResult(seq, vote.status, base.expected_hash,
                                  actual_hash, detail)

    # ------------------------------------------------------------------ #
    def is_valid(self) -> tuple[bool, str]:
        """Quorum is healthy if at least ``threshold`` witness chains are intact."""
        with self._lock:
            results = [w.is_valid() for w in self.witnesses]
        intact = sum(1 for ok, _ in results if ok)
        if intact >= self.threshold:
            bad = [self._names[i] for i, (ok, _) in enumerate(results) if not ok]
            if bad:
                return True, f"Quorum intact ({intact}/{self.nodes}); {', '.join(bad)} compromised but outvoted"
            return True, f"All {self.nodes} witnesses intact"
        return False, f"Quorum broken — only {intact}/{self.nodes} witnesses intact"

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        return self._primary.recent(n)

    def merkle_proof(self, seq: int) -> Optional[dict[str, Any]]:
        return self._primary.merkle_proof(seq)

    @staticmethod
    def verify_merkle_proof(leaf_hash: str, proof: list, root: str,
                            leaf_index: int) -> bool:
        return Blockchain.verify_merkle_proof(leaf_hash, proof, root, leaf_index)

    # ------------------------------------------------------------------ #
    # Dashboard / demo helpers
    # ------------------------------------------------------------------ #
    def status(self) -> dict[str, Any]:
        ok, msg = self.is_valid()
        per = []
        for name, w in zip(self._names, self.witnesses):
            valid, _ = w.is_valid()
            per.append({"name": name, "blocks": len(w), "valid": valid})
        return {"nodes": self.nodes, "threshold": self.threshold,
                "healthy": ok, "detail": msg, "witnesses": per}

    def tamper_witness(self, index: int, seq: int, forged_hash: str) -> bool:
        """DEMO ONLY: rewrite one witness's history for a seq, to show the quorum
        detects and outvotes a single compromised node.

        Forges both the lookup record (so the node *votes* a different hash) and
        the containing block's content (so the node's chain fails ``is_valid``) —
        exactly the "secretly rewrite history" attack the quorum defends against.
        """
        with self._lock:
            if not (0 <= index < self.nodes):
                return False
            w = self.witnesses[index]
            w.flush()                       # ensure the packet is sealed in a block
            w._anchored[seq] = forged_hash
            meta = w._anchor_meta.get(seq)
            if meta is not None:
                block = w.chain[meta["block_index"]]
                block.packet_hash = forged_hash   # breaks block.is_valid()
            return True
