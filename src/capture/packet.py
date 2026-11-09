"""PacketRecord — the normalized, source-agnostic packet model.

Every layer of PacketGuard speaks this one data structure. It can be produced
from a live Scapy packet (``PacketRecord.from_scapy``) or from synthetic data
(the simulation harness). Keeping one model means the detection engine does not
care whether a packet came off a real wire or a lab scenario.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


def sha256_hex(data: bytes) -> str:
    """Return the SHA-256 hex digest of ``data`` (the per-packet fingerprint)."""
    return hashlib.sha256(data).hexdigest()


@dataclass
class PacketRecord:
    """A single observed packet, normalized to the fields PacketGuard reasons about.

    Attributes
    ----------
    seq:
        Application-level monotonic sequence number assigned by the sender.
        Gaps in this sequence are how we detect loss/theft (Rule R001).
    payload_hash:
        SHA-256 over the payload bytes. This is what gets anchored on the
        blockchain and later re-computed by the receiver to detect tampering.
    """

    seq: int
    src_ip: str
    dst_ip: str
    protocol: str = "TCP"
    src_port: int = 0
    dst_port: int = 0
    size: int = 0
    ttl: int = 64
    tcp_flags: str = ""
    timestamp: float = field(default_factory=time.time)
    payload: bytes = b""
    payload_hash: str = ""
    # Free-form annotations (hop, interface, scenario label, ...).
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.payload_hash:
            self.payload_hash = sha256_hex(self.payload)
        if not self.size:
            self.size = len(self.payload)

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def from_scapy(cls, packet: Any, seq: Optional[int] = None) -> "PacketRecord":
        """Build a :class:`PacketRecord` from a live Scapy packet.

        Imported lazily so the whole project runs (and is testable) on machines
        without Scapy or without root privileges.
        """
        from scapy.layers.inet import IP, TCP, UDP  # type: ignore

        ip = packet.getlayer(IP)
        if ip is None:
            raise ValueError("Non-IP packet cannot be normalized")

        proto = "OTHER"
        sport = dport = 0
        flags = ""
        tcp_seq = None
        if packet.haslayer(TCP):
            proto = "TCP"
            tcp = packet.getlayer(TCP)
            sport, dport = int(tcp.sport), int(tcp.dport)
            flags = str(tcp.flags)
            tcp_seq = int(tcp.seq)
        elif packet.haslayer(UDP):
            proto = "UDP"
            udp = packet.getlayer(UDP)
            sport, dport = int(udp.sport), int(udp.dport)
        else:
            proto = {1: "ICMP"}.get(int(ip.proto), f"IP/{int(ip.proto)}")

        raw = bytes(packet)
        return cls(
            seq=seq if seq is not None else (tcp_seq or 0),
            src_ip=str(ip.src),
            dst_ip=str(ip.dst),
            protocol=proto,
            src_port=sport,
            dst_port=dport,
            size=len(raw),
            ttl=int(ip.ttl),
            tcp_flags=flags,
            payload=raw,
            payload_hash=sha256_hex(raw),
        )

    # ------------------------------------------------------------------ #
    # Serialization (for the dashboard API / SQLite logs)
    # ------------------------------------------------------------------ #
    def to_public_dict(self) -> dict[str, Any]:
        """JSON-safe view, omitting raw payload bytes."""
        d = asdict(self)
        d.pop("payload", None)
        return d

    @property
    def flow_key(self) -> tuple[str, str, int, int, str]:
        """5-tuple identifying the flow this packet belongs to."""
        return (self.src_ip, self.dst_ip, self.src_port, self.dst_port, self.protocol)
