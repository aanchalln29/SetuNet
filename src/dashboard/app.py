"""SETU-NET Disaster Mesh Monitoring and Operations Dashboard Server.

Serves the real-time emergency dashboard UI and REST API over a single shared
:class:`SetuNetEngine`. Uses Python's standard-library HTTP server with zero
external dependencies, matching the existing project architecture.

Features:
  - Interactive live mesh simulation driver
  - On-demand alert injection (SOS, Evacuation, Troop Movement, General)
  - Interactive node positioning (moving nodes in/out of 200m range)
  - Cryptographic audit and delivery report export
  - Real-time priority queue inspection and preemption tracking

Usage:
    python -m src.dashboard.app          # then open http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ..engine import SetuNetEngine
from ..mesh.protocol import AlertCategory, GPSLocation

try:
    from simulations import scenarios as scn
except Exception:  # pragma: no cover
    scn = None

HERE = os.path.dirname(__file__)
TEMPLATES = os.path.join(HERE, "templates")
STATIC = os.path.join(HERE, "static")

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

SCENARIO_MAP = {
    "normal_flood": "scenario_normal_multihop",
    "sos_preemption": "scenario_sos_preemption",
    "duplicate_storm": "scenario_duplicate_suppression",
    "ttl_expiration": "scenario_ttl_expiration",
    "tampered_signature": "scenario_tampered_signature",
    "ack_roundtrip": "scenario_ack_roundtrip",
    "store_and_carry": "scenario_sparse_network",
    "clock_skew": "scenario_clock_skew",
    "scale_50": "scenario_scalability_50_nodes",
}


class LiveDriver(threading.Thread):
    """Continuously feeds the mesh engine with realistic emergency alerts and telemetry."""

    def __init__(self, engine: SetuNetEngine, period: float = 2.5):
        super().__init__(name="setunet-livedriver", daemon=True)
        self.engine = engine
        self.period = period
        self.running = True
        self._stop = threading.Event()
        self._tick = 0
        
        self._messages_pool = [
            (AlertCategory.GENERAL, "Civic Shelter Alpha: Food and bottled water rations restocked."),
            (AlertCategory.TROOP_MOVEMENT, "Tactical Unit Bravo: Sector 3 perimeter secured; no civilian breaches."),
            (AlertCategory.GENERAL, "All-clear signal: North canal bridge inspection passed; pedestrian traffic safe."),
            (AlertCategory.EVACUATION, "Evacuation advisory: Rising floodwater in Sector 2, relocate to Higher Ridge."),
            (AlertCategory.TROOP_MOVEMENT, "Engineering squad moving 2 earthmovers towards River Embankment."),
            (AlertCategory.SOS, "URGENT SOS: Building collapse near Market Square, 6 people trapped! Immediate SAR required!"),
            (AlertCategory.GENERAL, "Medical post: First-aid station operational with 4 paramedics on duty."),
        ]

    def run(self) -> None:  # pragma: no cover - timing loop
        while not self._stop.is_set():
            if self.running:
                # Emit periodic realistic alert
                category, text = self._messages_pool[self._tick % len(self._messages_pool)]
                sender = random.choice(["phone-1", "phone-2", "phone-3", "phone-5"])
                
                # Low probability for SOS during automated background traffic, high for General/Troop
                if category == AlertCategory.SOS and random.random() > 0.35:
                    category = AlertCategory.GENERAL
                    text = f"Status report #{self._tick}: Relays operational, battery levels optimal."

                try:
                    self.engine.broadcast_alert(
                        sender_id=sender,
                        category=category,
                        payload_text=text,
                    )
                except Exception:
                    pass

                self._tick += 1
            self._stop.wait(self.period)

    def inject_named(self, key: str) -> dict[str, Any]:
        fn_name = SCENARIO_MAP.get(key)
        if not fn_name or not scn:
            return {"ok": False, "error": f"Unknown scenario: {key}"}
        fn = getattr(scn, fn_name, None)
        if not fn:
            return {"ok": False, "error": f"Scenario function {fn_name} not found"}

        result = fn(self.engine)
        return {
            "ok": result.passed,
            "name": result.name,
            "target": result.target_metric,
            "observed": result.observed_metric,
            "details": result.details,
        }

    def stop(self) -> None:
        self._stop.set()


class Handler(BaseHTTPRequestHandler):
    engine: SetuNetEngine = None  # type: ignore[assignment]
    driver: LiveDriver = None     # type: ignore[assignment]

    def log_message(self, fmt, *args):  # Quiet logging
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj: Any) -> None:
        self._send(200, json.dumps(obj).encode("utf-8"), _CONTENT_TYPES[".json"])

    def _send_file(self, path: str) -> None:
        if not os.path.isfile(path):
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        ext = os.path.splitext(path)[1]
        with open(path, "rb") as fh:
            self._send(200, fh.read(), _CONTENT_TYPES.get(ext, "application/octet-stream"))

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/":
            self._send_file(os.path.join(TEMPLATES, "index.html"))
        elif route == "/api/snapshot":
            self._send_json(self.engine.snapshot())
        elif route == "/api/health":
            self._send_json({
                "status": "operational",
                "system": "SETU-NET Emergency Mesh",
                "active_nodes": len(self.engine.nodes),
                "demo_running": self.driver.running if self.driver else False,
                "total_alerts": self.engine.stats.total_broadcasts,
                "total_delivered": self.engine.stats.total_delivered,
            })
        elif route == "/api/audit" or route == "/api/proof":
            params = parse_qs(urlparse(self.path).query)
            msg_id = params.get("message_id", [""])[0] or params.get("msg_id", [""])[0]
            
            # If no ID provided, pick the most recent alert
            if not msg_id and self.engine.recent_alerts:
                msg_id = self.engine.recent_alerts[0].message_id

            audit_data = self.engine.export_audit(msg_id)
            if not audit_data:
                self._send(404, b'{"error":"No audit record found for that message_id"}', _CONTENT_TYPES[".json"])
                return

            body = json.dumps(audit_data, indent=2).encode("utf-8")
            if params.get("download", ["0"])[0] == "1":
                self.send_response(200)
                self.send_header("Content-Type", _CONTENT_TYPES[".json"])
                self.send_header("Content-Disposition", f'attachment; filename="setunet-audit-{msg_id}.json"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._send(200, body, _CONTENT_TYPES[".json"])
        elif route.startswith("/static/"):
            rel_path = route[len("/static/"):].replace("/", os.sep)
            self._send_file(os.path.join(STATIC, rel_path))
        else:
            self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}

        if route == "/api/trigger" or route == "/api/trigger-alert":
            sender = payload.get("sender_id", "phone-1")
            cat_name = payload.get("category", "SOS")
            text = payload.get("payload_text", "Emergency broadcast notification.")
            ttl = int(payload.get("ttl", 6))
            lat = payload.get("lat")
            lon = payload.get("lon")
            loc = GPSLocation(float(lat), float(lon)) if lat and lon else None

            alert = self.engine.broadcast_alert(
                sender_id=sender,
                category=cat_name,
                payload_text=text,
                location=loc,
                initial_ttl=ttl,
            )
            self._send_json({"ok": True, "alert": alert.to_dict()})

        elif route == "/api/inject":
            scenario_key = payload.get("scenario", "")
            res = self.driver.inject_named(scenario_key) if self.driver else {"ok": False}
            self._send_json(res)

        elif route == "/api/demo":
            if self.driver:
                self.driver.running = bool(payload.get("running", True))
            self._send_json({"running": self.driver.running if self.driver else False})

        elif route == "/api/tamper":
            # Injects an intentionally tampered signature alert
            alert = self.engine.broadcast_alert(
                sender_id="phone-1",
                category=AlertCategory.SOS,
                payload_text="[SIMULATED ATTACK] Modified coordinates payload with forged signature.",
                tamper_signature=True,
            )
            self._send_json({
                "ok": True,
                "message": "Tampered alert injected and rejected by mesh nodes",
                "alert_id": alert.message_id,
                "rejections_count": self.engine.router.tampered_dropped_count,
            })

        elif route == "/api/move-node":
            node_id = payload.get("node_id", "phone-8")
            lat = float(payload.get("lat", 28.6145))
            lon = float(payload.get("lon", 77.2095))
            node = self.engine.nodes.get(node_id)
            if node:
                node.latitude = lat
                node.longitude = lon
                self._send_json({"ok": True, "node_id": node_id, "lat": lat, "lon": lon})
            else:
                self._send_json({"ok": False, "error": f"Node {node_id} not found"})
        else:
            self._send(404, b"Not found", "text/plain; charset=utf-8")


def create_server(host: str = "127.0.0.1", port: int = 8000, demo: bool = True) -> ThreadingHTTPServer:
    engine = SetuNetEngine()
    driver = LiveDriver(engine, period=2.5)
    if demo:
        driver.start()

    Handler.engine = engine
    Handler.driver = driver
    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd


def main() -> None:
    host = os.environ.get("SETUNET_HOST", "127.0.0.1")
    port = int(os.environ.get("SETUNET_PORT", "8000"))
    demo = os.environ.get("SETUNET_DEMO", "1") != "0"
    httpd = create_server(host, port, demo=demo)
    print("=" * 72)
    print("  SETU-NET Emergency Mesh Operations Dashboard")
    print(f"  Live UI & Topology Monitor  ->  http://{host}:{port}")
    print("  (Press Ctrl+C to stop; background simulation is", "ON)" if demo else "OFF)")
    print("=" * 72)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down SETU-NET dashboard...")
        httpd.shutdown()


if __name__ == "__main__":
    main()
