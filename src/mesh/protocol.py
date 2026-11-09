"""SETU-NET Message Protocol and Alert Specifications.

Defines the four emergency alert priority categories, message structures,
GPS coordinate tagging, TTL hop constraints, and acknowledgement (ACK) packets
as specified in Slides 4, 5, 6, and 7.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any, List, Optional


class AlertCategory(IntEnum):
    """Four emergency alert categories ordered by strict priority (Slide 4).
    
    Lower integer value = Higher priority in the transmission queue.
    """
    SOS = 0             # Life-threatening emergencies (Highest priority)
    EVACUATION = 1      # Instructions to leave an area (High priority)
    TROOP_MOVEMENT = 2  # Controlled or simulated unit-order (Medium priority)
    GENERAL = 3         # Status updates and all-clear messages (Low priority)

    @classmethod
    def from_str(cls, name: str) -> "AlertCategory":
        upper = name.strip().upper()
        if upper in ("SOS", "LIFE_THREATENING"):
            return cls.SOS
        if upper in ("EVACUATION", "EVAC"):
            return cls.EVACUATION
        if upper in ("TROOP_MOVEMENT", "TROOP", "TACTICAL"):
            return cls.TROOP_MOVEMENT
        return cls.GENERAL

    @property
    def label(self) -> str:
        return {
            AlertCategory.SOS: "SOS",
            AlertCategory.EVACUATION: "Evacuation",
            AlertCategory.TROOP_MOVEMENT: "Troop Movement",
            AlertCategory.GENERAL: "General",
        }[self]

    @property
    def badge_color(self) -> str:
        return {
            AlertCategory.SOS: "crit",     # Red / Urgent
            AlertCategory.EVACUATION: "warn", # Amber / High
            AlertCategory.TROOP_MOVEMENT: "tactical", # Cyan / Tactical
            AlertCategory.GENERAL: "ok",   # Green / Info
        }[self]


@dataclass
class GPSLocation:
    """Geographic coordinate representation for every alert (Slide 4 & 5)."""
    latitude: float
    longitude: float
    altitude_meters: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "lat": round(self.latitude, 6),
            "lon": round(self.longitude, 6),
            "alt": round(self.altitude_meters, 1),
        }


@dataclass
class AlertMessage:
    """Emergency alert packet formatted for phone-to-phone Wi-Fi mesh.
    
    Attributes:
        message_id: Unique identifier (e.g., SETU-ALERT-<uuid>)
        category: AlertCategory (SOS, EVACUATION, TROOP_MOVEMENT, GENERAL)
        origin_node_id: Device ID of the originating phone
        payload_text: Human-readable emergency instruction or status
        location: GPSLocation of the incident or sender
        timestamp: Creation Unix epoch timestamp
        ttl: Time-To-Live hop limit (initial TTL = 6, Slide 6)
        hop_count: Number of hops traversed so far (starts at 0)
        hop_path: Chronological list of relay phone IDs
        time_offset_est: Estimated clock offset relative to network time
        public_key: Hex string of sender's Ed25519 public key
        signature: Hex string of Ed25519 digital signature
        meta: Optional telemetry / simulated test metadata
    """
    message_id: str
    category: AlertCategory
    origin_node_id: str
    payload_text: str
    location: GPSLocation
    timestamp: float = field(default_factory=time.time)
    ttl: int = 6  # Initial TTL per Slide 6
    hop_count: int = 0
    hop_path: list[str] = field(default_factory=list)
    time_offset_est: float = 0.0
    public_key: str = ""
    signature: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def priority(self) -> int:
        return int(self.category)

    def canonical_bytes(self) -> bytes:
        """Returns stable, reproducible bytes of critical fields for signing/verification."""
        payload_dict = {
            "message_id": self.message_id,
            "category": self.category.name,
            "origin_node_id": self.origin_node_id,
            "payload_text": self.payload_text,
            "location": self.location.to_dict(),
            "timestamp": round(self.timestamp, 3),
        }
        return json.dumps(payload_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "category": self.category.name,
            "category_label": self.category.label,
            "priority": self.priority,
            "badge_color": self.category.badge_color,
            "origin_node_id": self.origin_node_id,
            "payload_text": self.payload_text,
            "location": self.location.to_dict(),
            "timestamp": self.timestamp,
            "time_offset_est": self.time_offset_est,
            "ttl": self.ttl,
            "hop_count": self.hop_count,
            "hop_path": list(self.hop_path),
            "public_key": self.public_key,
            "signature": self.signature,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AlertMessage":
        loc_data = data.get("location", {})
        loc = GPSLocation(
            latitude=float(loc_data.get("lat", 0.0)),
            longitude=float(loc_data.get("lon", 0.0)),
            altitude_meters=float(loc_data.get("alt", 0.0)),
        )
        cat_raw = data.get("category", "GENERAL")
        if isinstance(cat_raw, int):
            cat = AlertCategory(cat_raw)
        else:
            cat = AlertCategory.from_str(str(cat_raw))

        return cls(
            message_id=data.get("message_id", f"SETU-{uuid.uuid4().hex[:8]}"),
            category=cat,
            origin_node_id=data.get("origin_node_id", "unknown-phone"),
            payload_text=data.get("payload_text", ""),
            location=loc,
            timestamp=float(data.get("timestamp", time.time())),
            ttl=int(data.get("ttl", 6)),
            hop_count=int(data.get("hop_count", 0)),
            hop_path=list(data.get("hop_path", [])),
            time_offset_est=float(data.get("time_offset_est", 0.0)),
            public_key=data.get("public_key", ""),
            signature=data.get("signature", ""),
            meta=dict(data.get("meta", {})),
        )


@dataclass
class AckMessage:
    """Acknowledgement (ACK) packet reporting observed delivery back to sender (Slide 3 & 6)."""
    ack_id: str
    original_message_id: str
    alert_category: AlertCategory
    ack_node_id: str
    origin_node_id: str
    hops_to_node: int
    received_timestamp: float
    latency_ms: float
    return_path: list[str] = field(default_factory=list)
    status: str = "DELIVERED"
    signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ack_id": self.ack_id,
            "original_message_id": self.original_message_id,
            "alert_category": self.alert_category.name,
            "category_label": self.alert_category.label,
            "ack_node_id": self.ack_node_id,
            "origin_node_id": self.origin_node_id,
            "hops_to_node": self.hops_to_node,
            "received_timestamp": self.received_timestamp,
            "latency_ms": round(self.latency_ms, 2),
            "return_path": list(self.return_path),
            "status": self.status,
            "signature": self.signature,
        }
