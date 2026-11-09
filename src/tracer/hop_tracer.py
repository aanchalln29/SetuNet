"""HopTracer — locate *which hop* on the path is misbehaving.

When a finding fires, we want to point at a node, not just a flow. This traces the
route to a destination and flags hops with TTL/latency anomalies. It shells out to
the system ``traceroute`` when available; when it is not (no tooling, no
privileges, or a demo box), it returns a deterministic synthetic path so the rest
of the pipeline — and the dashboard — still has something concrete to show.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class Hop:
    number: int
    ip: str
    rtt_ms: float = 0.0
    flagged: bool = False
    reason: str = ""


@dataclass
class TraceResult:
    destination: str
    hops: list[Hop] = field(default_factory=list)
    synthetic: bool = False

    @property
    def suspect(self) -> Hop | None:
        return next((h for h in self.hops if h.flagged), None)


class HopTracer:
    def __init__(self, max_hops: int = 15, timeout: float = 2.0,
                 allow_system: bool = False):
        self.max_hops = max_hops
        self.timeout = timeout
        # Synthetic by default: a live traceroute sends real probes and is slow,
        # which is wrong for an in-process demo that may trace hundreds of times.
        # Opt in with allow_system=True when running against a real lab network.
        self.allow_system = allow_system

    def trace(self, destination: str) -> TraceResult:
        if self.allow_system and shutil.which("traceroute"):
            try:
                return self._real_trace(destination)
            except Exception:  # noqa: BLE001 - fall back to synthetic on any error
                pass
        return self._synthetic_trace(destination)

    def _real_trace(self, destination: str) -> TraceResult:  # pragma: no cover - env
        out = subprocess.run(
            ["traceroute", "-m", str(self.max_hops), "-w", str(int(self.timeout)),
             destination],
            capture_output=True, text=True, timeout=self.max_hops * self.timeout + 5,
        )
        hops: list[Hop] = []
        for line in out.stdout.splitlines()[1:]:
            parts = line.split()
            if not parts or not parts[0].isdigit():
                continue
            ip = next((p for p in parts if p.count(".") == 3), "*")
            rtt = next((float(p) for p in parts if _is_float(p)), 0.0)
            hops.append(Hop(number=int(parts[0]), ip=ip, rtt_ms=rtt))
        self._flag_anomalies(hops)
        return TraceResult(destination=destination, hops=hops, synthetic=False)

    def _synthetic_trace(self, destination: str) -> TraceResult:
        """Deterministic 4-hop path so demos are reproducible."""
        base = [
            Hop(1, "10.0.0.1", 0.4),
            Hop(2, "10.0.0.254", 1.1),
            Hop(3, "192.168.1.47", 9.8),   # the planted suspect hop
            Hop(4, destination, 2.0),
        ]
        base[2].flagged = True
        base[2].reason = "Latency spike + TTL anomaly observed at this hop"
        return TraceResult(destination=destination, hops=base, synthetic=True)

    def _flag_anomalies(self, hops: list[Hop]) -> None:
        if not hops:
            return
        rtts = [h.rtt_ms for h in hops if h.rtt_ms > 0]
        if not rtts:
            return
        avg = sum(rtts) / len(rtts)
        for h in hops:
            if h.rtt_ms > avg * 3 and h.rtt_ms > 5:
                h.flagged = True
                h.reason = f"Latency {h.rtt_ms:.1f}ms >> path average {avg:.1f}ms"


def _is_float(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False
