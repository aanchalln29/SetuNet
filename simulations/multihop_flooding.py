"""Demonstrates 8-phone multi-hop controlled flooding and reverse ACK collection (Slide 5 & 6).

Usage:
    python -m simulations.multihop_flooding
"""

from __future__ import annotations

import sys

if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.engine import SetuNetEngine
from simulations.scenarios import scenario_normal_multihop


def main():
    engine = SetuNetEngine()
    print("=" * 70)
    print(" SETU-NET — 8-Phone Multi-Hop Controlled Flooding Test")
    print("=" * 70)
    result = scenario_normal_multihop(engine)
    print(str(result))
    print(f" Details: {result.details}")
    print("=" * 70)


if __name__ == "__main__":
    main()
