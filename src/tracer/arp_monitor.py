"""ARPMonitor — baseline the ARP table and flag changes (the MitM tell).

ARP spoofing is how a man-in-the-middle inserts itself: it convinces hosts that
the attacker's MAC owns a trusted IP. We learn a known-good IP→MAC baseline, then
every refresh compares the live table against it. Any IP whose MAC changed is a
strong MitM indicator and drives Rule R008.

Reading the live table is best-effort (``arp -a``); if it is unavailable the
monitor works purely from whatever baseline/updates it is given, which is exactly
how the simulation harness exercises it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass

_ARP_LINE = re.compile(r"\(?(?P<ip>\d+\.\d+\.\d+\.\d+)\)?\s+at\s+(?P<mac>[0-9a-fA-F:]{11,17})")


@dataclass
class ArpChange:
    ip: str
    old_mac: str
    new_mac: str


class ARPMonitor:
    def __init__(self) -> None:
        self.baseline: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    def set_baseline(self, table: dict[str, str] | None = None) -> dict[str, str]:
        """Establish the trusted baseline, from ``table`` or the live system."""
        self.baseline = dict(table) if table is not None else self.read_system_table()
        return self.baseline

    def read_system_table(self) -> dict[str, str]:
        """Parse ``arp -a`` into an IP→MAC map (empty if unavailable)."""
        if not shutil.which("arp"):
            return {}
        try:  # pragma: no cover - environment dependent
            out = subprocess.run(["arp", "-a"], capture_output=True, text=True,
                                 timeout=5)
        except Exception:  # noqa: BLE001
            return {}
        table: dict[str, str] = {}
        for line in out.stdout.splitlines():
            m = _ARP_LINE.search(line)
            if m:
                table[m.group("ip")] = m.group("mac").lower()
        return table

    # ------------------------------------------------------------------ #
    def diff(self, current: dict[str, str]) -> list[ArpChange]:
        """Return the list of IPs whose MAC changed versus the baseline."""
        changes: list[ArpChange] = []
        for ip, mac in current.items():
            mac = mac.lower()
            known = self.baseline.get(ip)
            if known is not None and known.lower() != mac:
                changes.append(ArpChange(ip=ip, old_mac=known, new_mac=mac))
        return changes

    def check_system(self) -> list[ArpChange]:  # pragma: no cover - environment
        return self.diff(self.read_system_table())
