"""Block — a single link in the PacketGuard integrity chain.

Each block anchors one packet's fingerprint (or a Merkle root over a batch) plus
the hash of the previous block. Because every block commits to its predecessor,
altering any historical packet hash changes that block's hash, which breaks every
block after it — that cascade is what makes the ledger tamper-evident.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Block:
    index: int
    packet_hash: str          # SHA-256 of the packet, or a Merkle root for a batch
    prev_hash: str
    timestamp: float = field(default_factory=time.time)
    seq: int = -1             # application sequence number of the anchored packet
    sender_id: str = "unknown"
    nonce: int = 0
    merkle_root: str = ""     # set when the block anchors a batch
    hash: str = ""

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = self.compute_hash()

    def _payload(self) -> str:
        """Canonical string the block hash commits to (order matters)."""
        return (
            f"{self.index}|{self.packet_hash}|{self.prev_hash}|{self.timestamp}"
            f"|{self.seq}|{self.sender_id}|{self.merkle_root}|{self.nonce}"
        )

    def compute_hash(self) -> str:
        return hashlib.sha256(self._payload().encode()).hexdigest()

    def mine(self, difficulty: int) -> None:
        """Proof-of-work: find a nonce so the hash starts with ``difficulty`` zeros.

        Kept intentionally cheap (small difficulty) so the demo stays real-time;
        it exists to show *why* rewriting history is expensive, not to be fast money.
        """
        target = "0" * difficulty
        self.nonce = 0
        self.hash = self.compute_hash()
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()

    def is_valid(self) -> bool:
        """A block is internally valid if its stored hash matches its contents."""
        return self.hash == self.compute_hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "packet_hash": self.packet_hash,
            "prev_hash": self.prev_hash,
            "timestamp": self.timestamp,
            "seq": self.seq,
            "sender_id": self.sender_id,
            "nonce": self.nonce,
            "merkle_root": self.merkle_root,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Block":
        return cls(
            index=d["index"],
            packet_hash=d["packet_hash"],
            prev_hash=d["prev_hash"],
            timestamp=d["timestamp"],
            seq=d.get("seq", -1),
            sender_id=d.get("sender_id", "unknown"),
            nonce=d.get("nonce", 0),
            merkle_root=d.get("merkle_root", ""),
            hash=d["hash"],
        )

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Block(#{self.index} seq={self.seq} hash={self.hash[:12]}…)"
