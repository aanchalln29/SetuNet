"""Capture filters — decide which packets PacketGuard should care about.

Two layers of filtering:

* **BPF strings** (``build_bpf``) are pushed down into Scapy/libpcap so the kernel
  drops uninteresting traffic before it ever reaches Python — cheap and fast.
* **PacketFilter** runs in Python on the normalized :class:`PacketRecord`, for
  rules that are easier to express in code (IP ranges, size bounds).
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .packet import PacketRecord


def build_bpf(
    protocols: Optional[Iterable[str]] = None,
    ports: Optional[Iterable[int]] = None,
    hosts: Optional[Iterable[str]] = None,
) -> str:
    """Compose a Berkeley Packet Filter expression from high-level options."""
    clauses: list[str] = []
    if protocols:
        proto_clause = " or ".join(p.lower() for p in protocols)
        clauses.append(f"({proto_clause})")
    if ports:
        port_clause = " or ".join(f"port {int(p)}" for p in ports)
        clauses.append(f"({port_clause})")
    if hosts:
        host_clause = " or ".join(f"host {h}" for h in hosts)
        clauses.append(f"({host_clause})")
    return " and ".join(clauses)


@dataclass
class PacketFilter:
    """Python-side predicate over normalized packet records."""

    protocols: Optional[set[str]] = None
    ports: Optional[set[int]] = None
    cidrs: list[str] = field(default_factory=list)
    min_size: int = 0
    max_size: Optional[int] = None

    def _in_cidrs(self, ip: str) -> bool:
        if not self.cidrs:
            return True
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(addr in ipaddress.ip_network(c, strict=False) for c in self.cidrs)

    def allows(self, pkt: PacketRecord) -> bool:
        if self.protocols and pkt.protocol.upper() not in self.protocols:
            return False
        if self.ports and not (
            pkt.src_port in self.ports or pkt.dst_port in self.ports
        ):
            return False
        if self.min_size and pkt.size < self.min_size:
            return False
        if self.max_size is not None and pkt.size > self.max_size:
            return False
        if not (self._in_cidrs(pkt.src_ip) or self._in_cidrs(pkt.dst_ip)):
            return False
        return True
