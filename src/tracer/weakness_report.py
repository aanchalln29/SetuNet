"""WeaknessReport — turn a finding into a human "where & why" incident report.

This is the module that produces the SOURCE TRACE REPORT shown in the project
plan: it correlates a :class:`Finding` with a hop trace (and ARP evidence) to name
the suspect node, the likely attack, a confidence score, and the weakness that let
it happen. The report feeds both the dashboard and the fix suggester.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .hop_tracer import HopTracer, TraceResult

# How each rule maps to a human attack hypothesis + a rough confidence prior.
_ATTACK_MAP: dict[str, tuple[str, int]] = {
    "R001": ("Packet interception / selective dropping", 80),
    "R002": ("Man-in-the-Middle payload tampering", 92),
    "R003": ("Replay attack", 85),
    "R004": ("Denial-of-Service flood", 95),
    "R005": ("Automated spam / bot activity", 78),
    "R006": ("Data exfiltration", 74),
    "R007": ("Route hijack / new intercepting hop", 70),
    "R008": ("Man-in-the-Middle via ARP spoofing", 90),
}


@dataclass
class WeaknessReport:
    rule_id: str
    incident: str
    detected_at: float
    affected: str
    suspect_hop: str
    evidence: list[str]
    likely_attack: str
    confidence: int
    weakness: str
    trace: TraceResult | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        """ASCII report matching the format in PROJECT_PLAN.md."""
        when = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(self.detected_at))
        lines = [
            "SOURCE TRACE REPORT",
            "━" * 24,
            f"Incident:     {self.incident} (Rule {self.rule_id})",
            f"Detected At:  {when}",
            f"Affected:     {self.affected}",
            "",
            "Source of Issue:",
            f"  → Suspect: {self.suspect_hop}",
        ]
        for ev in self.evidence:
            lines.append(f"  → Evidence: {ev}")
        lines += [
            f"  → Weakness: {self.weakness}",
            "",
            f"Likely Attack: {self.likely_attack}",
            f"Confidence:   {self.confidence}%",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "incident": self.incident,
            "detected_at": self.detected_at,
            "affected": self.affected,
            "suspect_hop": self.suspect_hop,
            "evidence": self.evidence,
            "likely_attack": self.likely_attack,
            "confidence": self.confidence,
            "weakness": self.weakness,
            "hops": [h.__dict__ for h in self.trace.hops] if self.trace else [],
        }


_WEAKNESS_MAP: dict[str, str] = {
    "R001": "Unauthenticated path allows silent packet drops between hops",
    "R002": "Unencrypted segment permits payload modification in transit",
    "R003": "No nonce/timestamp freshness check on the receiver",
    "R004": "No ingress rate-limiting on the exposed service",
    "R005": "No content/repetition filtering on inbound traffic",
    "R006": "No egress filtering or DLP on outbound flows",
    "R007": "Route not pinned; TTL changes accepted without challenge",
    "R008": "Dynamic ARP accepted without inspection (no DAI / static ARP)",
}


def build_report(finding, tracer: HopTracer | None = None) -> WeaknessReport:
    """Correlate a :class:`~src.detection.anomaly_engine.Finding` into a report."""
    tracer = tracer or HopTracer()
    attack, base_conf = _ATTACK_MAP.get(finding.rule_id, ("Unknown anomaly", 50))

    evidence: list[str] = []
    trace: TraceResult | None = None
    suspect = finding.src_ip or "unknown"
    confidence = base_conf

    # ARP spoofing carries its own strong evidence; no trace needed.
    if finding.rule_id == "R008":
        evidence.append(
            f"ARP binding changed {finding.evidence.get('old_mac')} → "
            f"{finding.evidence.get('new_mac')}"
        )
    else:
        target = finding.dst_ip or finding.src_ip or "10.0.0.2"
        trace = tracer.trace(target)
        hop = trace.suspect
        if hop:
            suspect = f"Hop {hop.number}: {hop.ip}"
            evidence.append(hop.reason or "Anomalous hop on the path")
            confidence = min(99, confidence + 3)
        if trace.synthetic:
            evidence.append("(trace synthesized — live traceroute unavailable)")

    # Pull any rule-specific evidence the finding already carries.
    for key, label in (("rate", "rate"), ("missing", "missing seqs"),
                       ("expected", "expected hash"), ("detail", "detail")):
        if key in finding.evidence:
            val = finding.evidence[key]
            if key == "expected":
                val = f"{val[:16]}…" if isinstance(val, str) else val
            evidence.append(f"{label}: {val}")

    affected = f"seq {finding.seq}" if finding.seq >= 0 else f"source {finding.src_ip}"

    return WeaknessReport(
        rule_id=finding.rule_id,
        incident=finding.name,
        detected_at=finding.timestamp,
        affected=affected,
        suspect_hop=suspect,
        evidence=evidence,
        likely_attack=attack,
        confidence=confidence,
        weakness=_WEAKNESS_MAP.get(finding.rule_id, "Unspecified weakness"),
        trace=trace,
    )
