"""MerkleTree — batch many packet hashes into one root.

Anchoring every single packet as its own block is expensive. A Merkle tree lets
us commit to a whole batch of packets with a single root hash, while still being
able to prove that any one packet was included (via an audit path). This is the
same construction Bitcoin uses to summarize the transactions in a block.
"""

from __future__ import annotations

import hashlib
from typing import Optional


def _h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_pair(left: str, right: str) -> str:
    return _h((left + right).encode())


class MerkleTree:
    """A binary Merkle tree over a list of leaf hashes (hex strings)."""

    def __init__(self, leaves: list[str]):
        # Defensive copy; an empty tree has a well-defined root of hash("").
        self.leaves: list[str] = list(leaves) if leaves else [_h(b"")]
        self.levels: list[list[str]] = []
        self._build()

    def _build(self) -> None:
        level = list(self.leaves)
        self.levels = [level]
        while len(level) > 1:
            nxt: list[str] = []
            for i in range(0, len(level), 2):
                left = level[i]
                # Duplicate the last node when a level has an odd count.
                right = level[i + 1] if i + 1 < len(level) else left
                nxt.append(_hash_pair(left, right))
            level = nxt
            self.levels.append(level)

    @property
    def root(self) -> str:
        return self.levels[-1][0]

    def proof(self, index: int) -> list[tuple[str, str]]:
        """Return the audit path for leaf ``index`` as (position, sibling_hash)."""
        if not (0 <= index < len(self.leaves)):
            raise IndexError("leaf index out of range")
        path: list[tuple[str, str]] = []
        idx = index
        for level in self.levels[:-1]:
            if idx % 2 == 0:
                sibling = level[idx + 1] if idx + 1 < len(level) else level[idx]
                path.append(("right", sibling))
            else:
                path.append(("left", level[idx - 1]))
            idx //= 2
        return path

    @staticmethod
    def verify(leaf: str, index: int, proof: list[tuple[str, str]], root: str) -> bool:
        """Verify that ``leaf`` at ``index`` is committed to by ``root``."""
        computed = leaf
        for position, sibling in proof:
            if position == "left":
                computed = _hash_pair(sibling, computed)
            else:
                computed = _hash_pair(computed, sibling)
        return computed == root

    def __len__(self) -> int:
        return len(self.leaves)
