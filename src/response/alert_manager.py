"""AlertManager — assemble, store, and dispatch alerts.

An alert bundles everything an operator needs to act: the finding, the weakness
report (where/why), the suggested fixes, and the composed hardening action. Alerts
are kept in a ring buffer for the dashboard and optionally pushed to email/webhook
sinks. Delivery is best-effort and never crashes the detection pipeline.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

_SEVERITY_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


@dataclass
class Alert:
    id: int
    rule_id: str
    name: str
    severity: str
    summary: str
    src_ip: str
    dst_ip: str
    seq: int
    timestamp: float
    report: dict[str, Any] = field(default_factory=dict)
    remediation: dict[str, Any] = field(default_factory=dict)
    hardening: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "rule_id": self.rule_id, "name": self.name,
            "severity": self.severity, "summary": self.summary,
            "src_ip": self.src_ip, "dst_ip": self.dst_ip, "seq": self.seq,
            "timestamp": self.timestamp, "report": self.report,
            "remediation": self.remediation, "hardening": self.hardening,
        }


class AlertManager:
    def __init__(self, capacity: int = 200):
        self._alerts: deque[Alert] = deque(maxlen=capacity)
        self._counter = 0
        self._lock = threading.RLock()
        self._sinks: list[Callable[[Alert], None]] = []
        self.counts: dict[str, int] = {}

    def add_sink(self, sink: Callable[[Alert], None]) -> None:
        self._sinks.append(sink)

    def raise_alert(
        self,
        finding,
        report: Optional[dict[str, Any]] = None,
        remediation: Optional[dict[str, Any]] = None,
        hardening: Optional[dict[str, Any]] = None,
    ) -> Alert:
        with self._lock:
            self._counter += 1
            alert = Alert(
                id=self._counter, rule_id=finding.rule_id, name=finding.name,
                severity=finding.severity, summary=finding.summary,
                src_ip=finding.src_ip, dst_ip=finding.dst_ip, seq=finding.seq,
                timestamp=finding.timestamp, report=report or {},
                remediation=remediation or {}, hardening=hardening or {},
            )
            self._alerts.append(alert)
            self.counts[finding.rule_id] = self.counts.get(finding.rule_id, 0) + 1

        for sink in self._sinks:
            try:
                sink(alert)
            except Exception:  # noqa: BLE001 - a bad sink must not stop detection
                pass
        return alert

    # ------------------------------------------------------------------ #
    def recent(self, n: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [a.to_dict() for a in list(self._alerts)[-n:][::-1]]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            by_sev: dict[str, int] = {}
            for a in self._alerts:
                by_sev[a.severity] = by_sev.get(a.severity, 0) + 1
            return {"total": self._counter, "by_rule": dict(self.counts),
                    "by_severity": by_sev}


# ---------------------------------------------------------------------- #
# Dispatch sinks (opt-in)
# ---------------------------------------------------------------------- #
def make_webhook_sink(url: str, min_severity: str = "HIGH") -> Callable[[Alert], None]:
    """A sink that POSTs HIGH-severity alerts as JSON to a webhook (Slack/Discord)."""
    threshold = _SEVERITY_RANK.get(min_severity, 3)

    def sink(alert: Alert) -> None:  # pragma: no cover - network side effect
        if _SEVERITY_RANK.get(alert.severity, 0) < threshold:
            return
        payload = json.dumps({"text": f"[{alert.severity}] {alert.name}: {alert.summary}"})
        req = urllib.request.Request(url, data=payload.encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)

    return sink


def make_console_sink() -> Callable[[Alert], None]:
    def sink(alert: Alert) -> None:
        tag = {"HIGH": "[CRITICAL]", "MEDIUM": "[WARNING]", "LOW": "[INFO]"}.get(alert.severity, "[INFO]")
        ts = time.strftime("%H:%M:%S", time.localtime(alert.timestamp))
        print(f"{tag} [{ts}] {alert.rule_id} {alert.name} — {alert.summary}")

    return sink
