"""SETU-NET Mesh Network Package.

Infrastructure-independent emergency alerting over phone-to-phone Wi-Fi connections.
"""

from .ack_manager import AckManager, DeliveryReport
from .battery import BatteryMonitor, BatteryState
from .clock_sync import ClockSyncEstimator, PeerTimeOffset
from .crypto import KeyPair, generate_keypair, sign_message, verify_signature
from .duplicate_cache import DuplicateCache
from .mesh_router import MeshNode, MeshRouter, haversine_distance_meters
from .priority_queue import PriorityMeshQueue
from .protocol import AckMessage, AlertCategory, AlertMessage, GPSLocation
from .storage import MeshDatabase

__all__ = [
    "AlertCategory",
    "GPSLocation",
    "AlertMessage",
    "AckMessage",
    "KeyPair",
    "generate_keypair",
    "sign_message",
    "verify_signature",
    "DuplicateCache",
    "PriorityMeshQueue",
    "ClockSyncEstimator",
    "PeerTimeOffset",
    "BatteryMonitor",
    "BatteryState",
    "MeshDatabase",
    "AckManager",
    "DeliveryReport",
    "MeshNode",
    "MeshRouter",
    "haversine_distance_meters",
]
