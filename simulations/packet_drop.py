"""Packet-drop / theft simulation (R001).

Synthetic: the sender anchors a contiguous run of packets, four of which never
reach the receiver. PacketGuard sees the sequence gap and raises a loss/theft
alert, then traces the suspect hop.

    python -m simulations.packet_drop
"""

from __future__ import annotations

from src.engine import PacketGuardEngine
from simulations.scenarios import scenario_packet_drop


def main() -> None:
    engine = PacketGuardEngine(difficulty=1)
    print(scenario_packet_drop(engine))
    for alert in engine.alerts.recent(5):
        print(f"  • {alert['rule_id']} {alert['summary']}")
        report = alert.get("report", {})
        if report:
            print(f"    suspect: {report.get('suspect_hop')} "
                  f"({report.get('confidence')}% confidence)")


if __name__ == "__main__":
    main()
