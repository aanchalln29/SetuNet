"""Run every SETU-NET test scenario against fresh mesh engines and report verification results.

Usage:
    python -m simulations.run_demo

Each scenario verifies an objective from Slides 2 to 10 (Controlled Flooding,
SOS Preemption, Duplicate Suppression, TTL Expiration, Ed25519 Signatures,
Reverse ACK Trace, Clock Skew, and 50-Node Scalability).
"""

from __future__ import annotations

import sys

# Safe terminal encoding on Windows CP1252 / UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.engine import SetuNetEngine
from simulations.scenarios import ALL_SCENARIOS, scenario_normal_multihop


def main() -> int:
    print("=" * 80)
    print(" SETU-NET — Phone-to-Phone Emergency Mesh Simulation Suite")
    print(" Application-Layer Priority Alerts over Wi-Fi Direct / Wi-Fi Aware")
    print("=" * 80)

    # 1. Baseline Multi-Hop Test Rig Check (8 Phones)
    baseline_engine = SetuNetEngine()
    baseline = scenario_normal_multihop(baseline_engine)
    print(str(baseline))
    print("-" * 80)

    # 2. Run All Specific Objective Scenarios
    results = [baseline]
    for scenario in ALL_SCENARIOS[1:]:  # Scenarios 2 through 9
        engine = SetuNetEngine()  # Fresh isolated engine per test
        result = scenario(engine)
        results.append(result)
        print(str(result))

    print("-" * 80)
    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)
    print(f" Result: {passed_count}/{total_count} Objectives Verified Successfully")
    print("=" * 80)

    if passed_count == total_count:
        print(" [OK] All SETU-NET protocol specifications, security checks, and targets met.")
        return 0
    else:
        print(" [!] Some checks did not pass — see details above.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
