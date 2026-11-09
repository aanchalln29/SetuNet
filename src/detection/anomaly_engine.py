"""AnomalyEngine — the brain of the detection layer.

It receives every normalized :class:`PacketRecord`, consults the blockchain for
integrity verification, runs the per-signal detectors, and emits :class:`Finding`
objects keyed to the rule that fired (R001–R008). Rules and thresholds come from
``rules.json`` so behaviour is tunable without touching code.

TTL anomalies (R007) are tracked here directly; ARP spoofing (R008) is fed in
from the tracer's ARP monitor via :meth:`report_arp_change`.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..blockchain.chain import Blockchain
from ..capture.packet import PacketRecord
from .exfil_detector import ExfilDetector
from .sequence_tracker import SequenceTracker
from .spam_detector import SpamDetector

_RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.json")


@dataclass
class Finding:
    """One security finding, ready to become an alert."""

    rule_id: str
    name: str
    severity: str                      # HIGH | MEDIUM | LOW
    summary: str
    src_ip: str = ""
    dst_ip: str = ""
    seq: int = -1
    evidence: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "severity": self.severity,
            "summary": self.summary,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "seq": self.seq,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
        }


def load_rules(path: str = _RULES_PATH) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class AnomalyEngine:
    def __init__(self, blockchain: Blockchain, rules: Optional[dict[str, Any]] = None):
        self.blockchain = blockchain
        self.rules = rules or load_rules()
        self._by_id = {r["id"]: r for r in self.rules["rules"]}

        seq_p = self._params("R001")
        self.sequence = SequenceTracker(
            max_gap=seq_p.get("max_gap", 3),
            window_seconds=seq_p.get("window_seconds", 10),
        )
        spam_rate = self._params("R004")
        spam_rep = self._params("R005")
        self.spam = SpamDetector(
            packets_per_sec=spam_rate.get("packets_per_sec", 500),
            identical_payloads=spam_rep.get("identical_payloads", 50),
            repeat_window=spam_rep.get("window_seconds", 5),
        )
        exfil_p = self._params("R006")
        self.exfil = ExfilDetector(
            trusted_cidrs=self.rules.get("trusted_internal_cidrs", []),
            burst_bytes=exfil_p.get("burst_bytes", 10 * 1024 * 1024),
            window_seconds=exfil_p.get("window_seconds", 30),
            dns_txt_len=exfil_p.get("dns_txt_len", 100),
        )
        # Track a rolling baseline TTL per flow for R007.
        self._ttl_baseline: dict[tuple, int] = {}

    # ------------------------------------------------------------------ #
    def _params(self, rule_id: str) -> dict[str, Any]:
        rule = self._by_id.get(rule_id, {})
        return rule.get("params", {}) if rule.get("enabled", True) else {}

    def _enabled(self, rule_id: str) -> bool:
        return bool(self._by_id.get(rule_id, {}).get("enabled", False))

    def _rule(self, rule_id: str) -> dict[str, Any]:
        return self._by_id[rule_id]

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #
    def inspect(self, pkt: PacketRecord) -> list[Finding]:
        """Run every enabled detector against one packet; return findings."""
        findings: list[Finding] = []
        now = pkt.timestamp

        # Observe the sequence number once; both R001 (gaps) and R003 (duplicates)
        # read the result, so we must not call observe() twice per packet.
        newly_missing: list[int] = []
        is_duplicate = False
        if self._enabled("R001") or self._enabled("R003"):
            newly_missing, is_duplicate = self.sequence.observe(pkt.seq, now=now)

        # --- R002 Tampering & R001 loss rely on the blockchain anchor ---
        if self._enabled("R002"):
            result = self.blockchain.verify_packet(pkt.seq, pkt.payload_hash)
            if result.status == "tampered":
                r = self._rule("R002")
                findings.append(Finding(
                    rule_id="R002", name=r["name"], severity=r["severity"],
                    summary=f"Payload hash mismatch at seq {pkt.seq} — packet altered in transit",
                    src_ip=pkt.src_ip, dst_ip=pkt.dst_ip, seq=pkt.seq,
                    evidence={"expected": result.expected_hash,
                              "actual": result.actual_hash},
                ))

        # --- R003 Replay: same payload under a new seq, or a duplicate seq ---
        if self._enabled("R003"):
            spliced = self.blockchain.is_replay(pkt.payload_hash, pkt.seq)
            if spliced or is_duplicate:
                r = self._rule("R003")
                how = "duplicate sequence number" if is_duplicate else "hash seen before"
                findings.append(Finding(
                    rule_id="R003", name=r["name"], severity=r["severity"],
                    summary=f"Replayed packet at seq {pkt.seq} ({how})",
                    src_ip=pkt.src_ip, dst_ip=pkt.dst_ip, seq=pkt.seq,
                    evidence={"payload_hash": pkt.payload_hash, "duplicate": is_duplicate},
                ))

        # --- R001 Sequence gap (loss / theft) ---
        if self._enabled("R001"):
            gap = self.sequence.gap_exceeded(now=now)
            if gap:
                r = self._rule("R001")
                findings.append(Finding(
                    rule_id="R001", name=r["name"], severity=r["severity"],
                    summary=f"{len(gap.missing)} packets missing within "
                            f"{gap.window_seconds:.0f}s — possible loss/theft",
                    src_ip=pkt.src_ip, dst_ip=pkt.dst_ip, seq=pkt.seq,
                    evidence={"missing": gap.missing},
                ))

        # --- R004 Flood / DoS ---
        if self._enabled("R004"):
            verdict = self.spam.observe_rate(pkt.src_ip, now=now)
            if verdict.flooding:
                r = self._rule("R004")
                findings.append(Finding(
                    rule_id="R004", name=r["name"], severity=r["severity"],
                    summary=f"{pkt.src_ip} sending {verdict.rate:.0f} pkts/s — flood/DoS",
                    src_ip=pkt.src_ip, dst_ip=pkt.dst_ip, seq=pkt.seq,
                    evidence={"rate": verdict.rate,
                              "threshold": self.spam.packets_per_sec},
                ))

        # --- R005 Spam (identical payloads) ---
        if self._enabled("R005"):
            count = self.spam.observe_payload(pkt.src_ip, pkt.payload_hash, now=now)
            if count:
                r = self._rule("R005")
                findings.append(Finding(
                    rule_id="R005", name=r["name"], severity=r["severity"],
                    summary=f"{count} identical payloads from {pkt.src_ip} — spam bot",
                    src_ip=pkt.src_ip, dst_ip=pkt.dst_ip, seq=pkt.seq,
                    evidence={"repeat_count": count},
                ))

        # --- R006 Exfiltration ---
        if self._enabled("R006"):
            event = self.exfil.observe(
                pkt.src_ip, pkt.dst_ip, pkt.size, pkt.protocol,
                dns_qname_len=int(pkt.meta.get("dns_qname_len", 0)), now=now,
            )
            if event:
                r = self._rule("R006")
                findings.append(Finding(
                    rule_id="R006", name=r["name"], severity=r["severity"],
                    summary=f"Possible exfiltration ({event.kind}): {event.detail}",
                    src_ip=pkt.src_ip, dst_ip=pkt.dst_ip, seq=pkt.seq,
                    evidence={"kind": event.kind, "detail": event.detail,
                              "bytes": event.bytes_total},
                ))

        # --- R007 TTL anomaly (route hijack) ---
        if self._enabled("R007"):
            finding = self._check_ttl(pkt)
            if finding:
                findings.append(finding)

        return findings

    def _check_ttl(self, pkt: PacketRecord) -> Optional[Finding]:
        key = (pkt.src_ip, pkt.dst_ip)
        ratio = self._params("R007").get("ttl_drop_ratio", 0.5)
        baseline = self._ttl_baseline.get(key)
        if baseline is None:
            self._ttl_baseline[key] = pkt.ttl
            return None
        if baseline > 0 and pkt.ttl < baseline * (1 - ratio):
            r = self._rule("R007")
            finding = Finding(
                rule_id="R007", name=r["name"], severity=r["severity"],
                summary=f"TTL dropped {baseline}→{pkt.ttl} on {pkt.src_ip}→{pkt.dst_ip} "
                        f"— a new hop may be intercepting this route",
                src_ip=pkt.src_ip, dst_ip=pkt.dst_ip, seq=pkt.seq,
                evidence={"baseline_ttl": baseline, "observed_ttl": pkt.ttl},
            )
            # Adopt the new TTL so we alert on the change, not every packet after.
            self._ttl_baseline[key] = pkt.ttl
            return finding
        # Slowly track legitimate TTL (take the max seen to resist spoofed lows).
        self._ttl_baseline[key] = max(baseline, pkt.ttl)
        return None

    # ------------------------------------------------------------------ #
    # R008 is driven externally by the ARP monitor.
    # ------------------------------------------------------------------ #
    def report_arp_change(self, ip: str, old_mac: str, new_mac: str) -> Optional[Finding]:
        if not self._enabled("R008"):
            return None
        r = self._rule("R008")
        return Finding(
            rule_id="R008", name=r["name"], severity=r["severity"],
            summary=f"ARP binding for {ip} changed {old_mac} → {new_mac} — MitM/ARP spoof",
            src_ip=ip,
            evidence={"old_mac": old_mac, "new_mac": new_mac},
        )
