"""PacketSniffer — the capture engine.

In production this wraps Scapy's live ``sniff`` (needs root + a real interface).
Because that environment is rarely available for coursework demos, Scapy is an
*optional* dependency: if it is missing or sniffing is not permitted, the engine
still runs and the simulation harness feeds it synthetic traffic instead.

Both paths emit the same :class:`PacketRecord` to a single callback, so nothing
downstream can tell the difference.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from .filters import build_bpf
from .packet import PacketRecord

# Scapy is optional — import lazily and record availability.
try:  # pragma: no cover - environment dependent
    from scapy.all import sniff as _scapy_sniff  # type: ignore
    SCAPY_AVAILABLE = True
except Exception:  # noqa: BLE001 - any import failure means "not available"
    _scapy_sniff = None
    SCAPY_AVAILABLE = False


PacketCallback = Callable[[PacketRecord], None]


class PacketSniffer:
    """Capture live packets and forward normalized records to a callback."""

    def __init__(
        self,
        on_packet: PacketCallback,
        iface: Optional[str] = None,
        protocols: Optional[list[str]] = None,
        ports: Optional[list[int]] = None,
        hosts: Optional[list[str]] = None,
    ):
        self.on_packet = on_packet
        self.iface = iface
        self.bpf = build_bpf(protocols, ports, hosts)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._seq = 0

    @property
    def available(self) -> bool:
        return SCAPY_AVAILABLE

    def _handle(self, scapy_packet) -> None:  # pragma: no cover - needs live NIC
        try:
            record = PacketRecord.from_scapy(scapy_packet, seq=self._seq)
        except ValueError:
            return  # skip non-IP packets
        self._seq += 1
        self.on_packet(record)

    def start(self) -> bool:
        """Start live capture in a background thread. Returns False if unavailable."""
        if not SCAPY_AVAILABLE:
            return False
        self._stop.clear()

        def _run() -> None:  # pragma: no cover - needs live NIC + root
            _scapy_sniff(
                prn=self._handle,
                filter=self.bpf or None,
                iface=self.iface,
                store=False,
                stop_filter=lambda _pkt: self._stop.is_set(),
            )

        self._thread = threading.Thread(target=_run, name="packetguard-sniffer",
                                        daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():  # pragma: no cover
            self._thread.join(timeout=2.0)

    def feed(self, record: PacketRecord) -> None:
        """Inject a record as if it had been sniffed (used by the simulator)."""
        self.on_packet(record)
