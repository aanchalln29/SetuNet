"""MitM simulation — tampering (R002) and ARP spoofing (R008).

Synthetic, in-process demonstration. In a real isolated lab you would reproduce
this between nodes with ettercap/arpspoof; here we fabricate the same observable
effects (an altered payload, and a changed ARP binding) and confirm PacketGuard
catches both.

    python -m simulations.mitm_attack
"""

from __future__ import annotations

from src.engine import PacketGuardEngine
from simulations.scenarios import scenario_arp_spoof, scenario_tampering


def main() -> None:
    engine = PacketGuardEngine(difficulty=1)
    for scenario in (scenario_tampering, scenario_arp_spoof):
        result = scenario(engine)
        print(result)
    for alert in engine.alerts.recent(10):
        print(f"  • {alert['rule_id']} {alert['name']}: {alert['summary']}")


if __name__ == "__main__":
    main()
