"""Replay-attack simulation (R003).

Synthetic: a legitimate authenticated packet is captured and re-injected under a
new sequence number. PacketGuard recognizes the repeated payload hash and flags
the replay.

    python -m simulations.replay_attack
"""

from __future__ import annotations

from src.engine import PacketGuardEngine
from simulations.scenarios import scenario_replay


def main() -> None:
    engine = PacketGuardEngine(difficulty=1)
    print(scenario_replay(engine))
    for alert in engine.alerts.recent(5):
        print(f"  • {alert['rule_id']} {alert['summary']}")


if __name__ == "__main__":
    main()
