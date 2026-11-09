"""AutoHardener — translate a remediation into a concrete host command.

Safety first: this class is **dry-run by default**. It composes the exact command
it *would* run (iptables rate-limit, block, static ARP, …) and records it, but does
not execute anything unless constructed with ``live=True`` *and* the caller passes
``confirm=True``. For coursework and the dashboard demo, dry-run is the right mode —
you can see and discuss the remediation without touching a real firewall.

Nothing here attacks anything; every action is a *defensive* control applied to the
operator's own host.
"""

from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HardeningAction:
    description: str
    command: list[str]
    applied: bool = False
    dry_run: bool = True
    result: str = ""
    timestamp: float = field(default_factory=time.time)

    @property
    def command_str(self) -> str:
        return " ".join(shlex.quote(c) for c in self.command)

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "command": self.command_str,
            "applied": self.applied,
            "dry_run": self.dry_run,
            "result": self.result,
            "timestamp": self.timestamp,
        }


class AutoHardener:
    def __init__(self, live: bool = False):
        # live=False => never executes, only composes commands.
        self.live = live
        self.history: list[HardeningAction] = []

    # ------------------------------------------------------------------ #
    def plan(self, auto_action: dict[str, Any]) -> HardeningAction | None:
        """Compose (but do not run) the command for an auto_action spec."""
        kind = auto_action.get("type")
        target = auto_action.get("target")
        if not kind or not target:
            return None

        if kind == "rate_limit":
            return HardeningAction(
                f"Rate-limit source {target} to 10 pkts/s",
                ["iptables", "-A", "INPUT", "-s", str(target), "-m", "limit",
                 "--limit", "10/second", "-j", "ACCEPT"],
            )
        if kind == "block_ip":
            return HardeningAction(
                f"Block traffic to/from {target}",
                ["iptables", "-A", "OUTPUT", "-d", str(target), "-j", "DROP"],
            )
        if kind == "firewall_isolate":
            return HardeningAction(
                f"Isolate suspect host {target}",
                ["iptables", "-A", "INPUT", "-s", str(target), "-j", "DROP"],
            )
        if kind == "static_arp":
            return HardeningAction(
                f"Pin a static ARP entry for {target} (operator must supply MAC)",
                ["arp", "-s", str(target), "<trusted-mac>"],
            )
        return None

    def apply(self, auto_action: dict[str, Any], confirm: bool = False) -> HardeningAction | None:
        """Plan the action, and execute it only if live+confirmed."""
        action = self.plan(auto_action)
        if action is None:
            return None

        if self.live and confirm and "<" not in action.command_str:
            try:  # pragma: no cover - would modify the host firewall
                proc = subprocess.run(action.command, capture_output=True, text=True,
                                     timeout=10)
                action.applied = proc.returncode == 0
                action.dry_run = False
                action.result = proc.stdout + proc.stderr
            except Exception as exc:  # noqa: BLE001
                action.result = f"error: {exc}"
        else:
            action.dry_run = True
            action.result = "DRY-RUN — command composed but not executed"

        self.history.append(action)
        return action
