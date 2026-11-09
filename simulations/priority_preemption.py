"""Demonstrates SOS preemption over lower-priority queued messages (Slide 4, 6 & 8).

Usage:
    python -m simulations.priority_preemption
"""

from __future__ import annotations

import sys

if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.engine import SetuNetEngine
from simulations.scenarios import scenario_sos_preemption


def main():
    engine = SetuNetEngine()
    print("=" * 70)
    print(" SETU-NET — Priority Preemption Demonstration")
    print(" Demonstrating SOS (P0) leaping ahead of General (P3) in relay queue")
    print("=" * 70)
    result = scenario_sos_preemption(engine)
    print(str(result))
    print(f" Details: {result.details}")
    print("=" * 70)


if __name__ == "__main__":
    main()
