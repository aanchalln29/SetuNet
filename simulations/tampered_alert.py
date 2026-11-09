"""Demonstrates Ed25519 signature verification and rejection of forged alerts (Slide 7).

Usage:
    python -m simulations.tampered_alert
"""

from __future__ import annotations

import sys

if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.engine import SetuNetEngine
from simulations.scenarios import scenario_tampered_signature


def main():
    engine = SetuNetEngine()
    print("=" * 70)
    print(" SETU-NET — Ed25519 Cryptographic Tamper Rejection Test")
    print("=" * 70)
    result = scenario_tampered_signature(engine)
    print(str(result))
    print(f" Details: {result.details}")
    print("=" * 70)


if __name__ == "__main__":
    main()
