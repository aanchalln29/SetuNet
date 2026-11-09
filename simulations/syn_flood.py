"""SYN-flood / DoS simulation (R004) and spam flood (R005).

Synthetic: a single source emits a burst far above the per-second rate threshold,
plus a run of identical payloads. PacketGuard rate-limits the source (dry-run) and
raises flood/spam alerts. In a real lab this maps to `hping3 --flood -S`, run only
against an isolated target you own.

    python -m simulations.syn_flood
"""

from __future__ import annotations

from src.engine import PacketGuardEngine
from simulations.scenarios import scenario_spam, scenario_syn_flood


def main() -> None:
    engine = PacketGuardEngine(difficulty=1)
    for scenario in (scenario_syn_flood, scenario_spam):
        print(scenario(engine))
    print(f"  suppressed duplicate alerts: {engine._suppressed}")
    for alert in engine.alerts.recent(5):
        hardening = alert.get("hardening") or {}
        print(f"  • {alert['rule_id']} {alert['summary']}")
        if hardening:
            print(f"    auto-fix (dry-run): {hardening.get('command')}")


if __name__ == "__main__":
    main()
