"""ExfilDetector — spot data leaving the network in suspicious ways (R006).

Data exfiltration is quiet by design, so we watch for two tells:

* **Volume bursts:** a lot of bytes flowing *outbound* to a single external IP
  inside a short window — classic bulk siphoning.
* **DNS tunneling:** abnormally long DNS queries (data smuggled inside TXT-style
  labels), which look nothing like normal name lookups.

"External" is anything outside the configured trusted internal CIDRs.
"""

from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class ExfilEvent:
    dst_ip: str
    kind: str          # "volume" | "dns_tunnel"
    detail: str
    bytes_total: int = 0


class ExfilDetector:
    def __init__(
        self,
        trusted_cidrs: list[str],
        burst_bytes: int = 10 * 1024 * 1024,
        window_seconds: float = 30.0,
        dns_txt_len: int = 100,
    ):
        self.trusted = [ipaddress.ip_network(c, strict=False) for c in trusted_cidrs]
        self.burst_bytes = burst_bytes
        self.window_seconds = window_seconds
        self.dns_txt_len = dns_txt_len
        # dst_ip -> deque of (timestamp, size)
        self._outbound: dict[str, deque[tuple[float, int]]] = defaultdict(deque)

    def _is_external(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return not any(addr in net for net in self.trusted)

    def observe(
        self,
        src_ip: str,
        dst_ip: str,
        size: int,
        protocol: str,
        dns_qname_len: int = 0,
        now: float | None = None,
    ) -> ExfilEvent | None:
        now = time.time() if now is None else now

        # DNS tunneling: long query names on UDP/53-style traffic.
        if protocol.upper() == "UDP" and dns_qname_len >= self.dns_txt_len:
            return ExfilEvent(dst_ip=dst_ip, kind="dns_tunnel",
                              detail=f"DNS query name length {dns_qname_len} bytes "
                                     f"(threshold {self.dns_txt_len})")

        # Volume bursts only matter when leaving the trusted network.
        if not (self._is_external(dst_ip) and not self._is_external(src_ip)):
            return None

        q = self._outbound[dst_ip]
        q.append((now, size))
        cutoff = now - self.window_seconds
        while q and q[0][0] < cutoff:
            q.popleft()
        total = sum(sz for _, sz in q)
        if total > self.burst_bytes:
            return ExfilEvent(dst_ip=dst_ip, kind="volume",
                              detail=f"{total / 1_048_576:.1f} MB to {dst_ip} in "
                                     f"{self.window_seconds:.0f}s",
                              bytes_total=total)
        return None
