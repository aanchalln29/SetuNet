"""SQLite Storage Engine for SETU-NET Alerts, ACKs, and Benchmark Test Logs.

Fulfills Slide 7 specification:
'SQLite will store the alert history, acknowledgements and relevant test logs.'
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, List, Optional

from .protocol import AckMessage, AlertCategory, AlertMessage, GPSLocation


class MeshDatabase:
    """Thread-safe SQLite database manager for SETU-NET nodes and EOC stations."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = threading.RLock()
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS alerts (
                    message_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    origin_node_id TEXT NOT NULL,
                    payload_text TEXT NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    altitude REAL,
                    timestamp REAL NOT NULL,
                    ttl INTEGER NOT NULL,
                    hop_count INTEGER NOT NULL,
                    hop_path_json TEXT,
                    public_key TEXT,
                    signature TEXT,
                    status TEXT DEFAULT 'ACTIVE',
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS acknowledgements (
                    ack_id TEXT PRIMARY KEY,
                    original_message_id TEXT NOT NULL,
                    alert_category TEXT NOT NULL,
                    ack_node_id TEXT NOT NULL,
                    origin_node_id TEXT NOT NULL,
                    hops_to_node INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    received_timestamp REAL NOT NULL,
                    return_path_json TEXT,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (original_message_id) REFERENCES alerts(message_id)
                );

                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    role TEXT NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    battery_pct REAL DEFAULT 100.0,
                    status TEXT DEFAULT 'ONLINE',
                    last_seen REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS test_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    node_id TEXT,
                    message_id TEXT,
                    details_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_alerts_cat ON alerts(category);
                CREATE INDEX IF NOT EXISTS idx_acks_msg ON acknowledgements(original_message_id);
                CREATE INDEX IF NOT EXISTS idx_logs_event ON test_logs(event_type);
            """)
            self._conn.commit()

    def save_alert(self, alert: AlertMessage, status: str = "DELIVERED") -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO alerts (
                    message_id, category, priority, origin_node_id, payload_text,
                    latitude, longitude, altitude, timestamp, ttl, hop_count,
                    hop_path_json, public_key, signature, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.message_id,
                alert.category.name,
                alert.priority,
                alert.origin_node_id,
                alert.payload_text,
                alert.location.latitude,
                alert.location.longitude,
                alert.location.altitude_meters,
                alert.timestamp,
                alert.ttl,
                alert.hop_count,
                json.dumps(alert.hop_path),
                alert.public_key,
                alert.signature,
                status,
                time.time(),
            ))
            self._conn.commit()

    def save_ack(self, ack: AckMessage) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO acknowledgements (
                    ack_id, original_message_id, alert_category, ack_node_id,
                    origin_node_id, hops_to_node, latency_ms, received_timestamp,
                    return_path_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ack.ack_id,
                ack.original_message_id,
                ack.alert_category.name,
                ack.ack_node_id,
                ack.origin_node_id,
                ack.hops_to_node,
                ack.latency_ms,
                ack.received_timestamp,
                json.dumps(ack.return_path),
                ack.status,
                time.time(),
            ))
            self._conn.commit()

    def register_node(
        self,
        node_id: str,
        label: str,
        role: str,
        lat: float,
        lon: float,
        battery_pct: float = 100.0,
        status: str = "ONLINE",
    ) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO nodes (
                    node_id, label, role, latitude, longitude, battery_pct, status, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (node_id, label, role, lat, lon, battery_pct, status, time.time()))
            self._conn.commit()

    def log_event(self, event_type: str, message_id: str | None = None,
                  node_id: str | None = None, details: dict | None = None) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT INTO test_logs (timestamp, event_type, node_id, message_id, details_json)
                VALUES (?, ?, ?, ?, ?)
            """, (time.time(), event_type, node_id, message_id, json.dumps(details or {})))
            self._conn.commit()

    def get_recent_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["hop_path"] = json.loads(d["hop_path_json"] or "[]")
                results.append(d)
            return results

    def get_acks_for_message(self, message_id: str) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                SELECT * FROM acknowledgements WHERE original_message_id = ?
                ORDER BY hops_to_node ASC, latency_ms ASC
            """, (message_id,))
            rows = cur.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["return_path"] = json.loads(d["return_path_json"] or "[]")
                results.append(d)
            return results

    def get_all_nodes(self) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM nodes ORDER BY node_id ASC")
            return [dict(r) for r in cur.fetchall()]

    def stats(self) -> dict[str, int]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) FROM alerts")
            total_alerts = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM acknowledgements")
            total_acks = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM nodes")
            total_nodes = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM test_logs")
            total_logs = cur.fetchone()[0]
            return {
                "total_alerts": total_alerts,
                "total_acks": total_acks,
                "total_nodes": total_nodes,
                "total_logs": total_logs,
            }

    def close(self) -> None:
        with self._lock:
            self._conn.close()
