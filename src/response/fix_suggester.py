"""FixSuggester — map a detected threat to specific, actionable remediation.

This is the "so what do I do about it" layer. Each rule maps to a ranked set of
fixes drawn from the remediation table in PROJECT_PLAN.md, plus a flag for whether
any of them can be auto-applied (handled by :mod:`auto_hardener`, always dry-run by
default). Fixes are concrete — "block 10.0.0.47", not "improve security".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Remediation:
    threat: str
    fixes: list[str]
    auto_apply: str            # "yes" | "partial" | "manual"
    auto_action: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "threat": self.threat,
            "fixes": self.fixes,
            "auto_apply": self.auto_apply,
            "auto_action": self.auto_action,
        }


class FixSuggester:
    """Produces remediation guidance for a finding."""

    def suggest(self, finding) -> Remediation:
        rid = finding.rule_id
        src = finding.src_ip or "<source-ip>"

        if rid == "R002":  # Tampering
            return Remediation(
                "Packet Tampering",
                ["Enable TLS/SSL on the affected segment",
                 "Establish an IPSec tunnel between the suspect hops",
                 "Rotate the encryption keys for this channel"],
                "partial",
                {"type": "firewall_isolate", "target": finding.src_ip},
            )
        if rid == "R001":  # Loss / theft
            return Remediation(
                "Packet Loss / Theft",
                ["Investigate the suspicious hop identified in the trace",
                 "Enable port security (MAC binding) on the switch",
                 "Deploy VLAN segmentation to isolate the path"],
                "manual",
            )
        if rid == "R003":  # Replay
            return Remediation(
                "Replay Attack",
                ["Enforce nonce/timestamp verification on the receiver",
                 "Enable anti-replay windows in IPSec",
                 "Add per-session tokens to the protocol"],
                "partial",
            )
        if rid in ("R004", "R005"):  # Flood / spam
            return Remediation(
                "Spam / DoS Flood",
                [f"Rate-limit the source IP {src}",
                 "Deploy SYN cookies on the target service",
                 "Enable DDoS mitigation (e.g. fail2ban)"],
                "yes",
                {"type": "rate_limit", "target": finding.src_ip},
            )
        if rid == "R006":  # Exfiltration
            return Remediation(
                "Data Exfiltration",
                [f"Block the external destination {finding.dst_ip or '<dst-ip>'}",
                 "Investigate the source host for compromise",
                 "Enable DLP policies on egress traffic"],
                "partial",
                {"type": "block_ip", "target": finding.dst_ip},
            )
        if rid == "R007":  # Route hijack
            return Remediation(
                "Route Hijack",
                ["Pin the route / verify the path to the destination",
                 "Enable route authentication where supported",
                 "Alert the network team to the new hop"],
                "manual",
            )
        if rid == "R008":  # ARP spoof / MitM
            return Remediation(
                "ARP Spoofing (MitM)",
                ["Enable Dynamic ARP Inspection (DAI) on the switch",
                 "Pin static ARP entries for critical hosts",
                 "Deploy 802.1X port authentication"],
                "manual",
                {"type": "static_arp", "target": finding.src_ip},
            )
        return Remediation("Unknown", ["Manual investigation required"], "manual")
