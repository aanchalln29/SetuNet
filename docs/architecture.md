# SETU-NET — Technical Architecture

This document describes the architectural layers, data structures, and algorithms of **SETU-NET**, an application-layer multi-hop emergency alert system over phone-to-phone Wi-Fi connections.

---

## 1. System Overview

SETU-NET enables direct, infrastructure-independent peer-to-phone emergency alerting across four primary functional layers:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   SETU-NET Application & UI Layer                     │
│        (Jetpack Compose Mobile App / Dashboard Operations Console)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                  Mesh Routing & Flow Control Layer                     │
│  - Controlled Flooding Engine       - TTL Hop Limitation (Initial=6)  │
│  - PriorityMeshQueue (SOS Preempt)   - Duplicate Suppression Cache      │
│  - Reverse ACK Delivery Trace       - Store-and-Carry Buffer           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│             Cryptographic Security & Verification Layer                │
│  - Ed25519 Asymmetric Signatures   - GPS Coordinates Verification     │
│  - Canonical JSON Serialization     - Clock Skew Estimation Filter     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                    Physical & Transport Layer                          │
│  - Wi-Fi Direct (P2P Sockets)       - Wi-Fi Aware (NAN Service)        │
│  - Google Nearby Connections        - 150m-200m RF Range Model         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Modules in `src/mesh/`

### 2.1 Protocol Specifications (`src/mesh/protocol.py`)
- Defines the four emergency alert categories: `SOS` (P0), `EVACUATION` (P1), `TROOP_MOVEMENT` (P2), and `GENERAL` (P3).
- Specifies canonical JSON serialization for signing.
- Defines `AlertMessage` and `AckMessage` data structures.

### 2.2 Cryptographic Engine (`src/mesh/crypto.py`)
- Implements **Ed25519** (RFC 8032) signing and verification.
- Includes pure-Python mathematical implementation with zero external dependencies and hardware acceleration support via native cryptography if installed.
- Verifies message integrity: any modification to alert text, GPS coordinates, or timestamp causes immediate signature failure and packet drop.

### 2.3 Priority Mesh Queue (`src/mesh/priority_queue.py`)
- Heap-based priority queue ordered by `(priority, timestamp)`.
- Preemption engine: an incoming SOS (P0) alert jumps to the head of the dispatch queue, passing any queued Evacuation, Troop Movement, or General orders.

### 2.4 Duplicate Suppression Cache (`src/mesh/duplicate_cache.py`)
- LRU cache with timestamp windowing.
- Prevents broadcast storms and routing loops by detecting whether a message ID has already been processed by the phone.

### 2.5 Clock Skew Estimator (`src/mesh/clock_sync.py`)
- Calculates peer-to-peer relative time differences using symmetric two-way timestamp exchange without requiring cellular connection or GPS time lock.

### 2.6 Mesh Router (`src/mesh/mesh_router.py`)
- Orchestrates controlled flooding across nearby peer nodes within 150m to 200m range.
- Implements initial TTL = 6 countdown.
- Manages store-and-carry buffering for disconnected nodes.

### 2.7 Acknowledgement Manager (`src/mesh/ack_manager.py`)
- Generates reverse delivery acknowledgements (ACKs) at each receiving phone.
- Tracks reverse hop path, per-hop latency, end-to-end latency, and computes delivery ratio (%) against performance targets.

### 2.8 SQLite Storage (`src/mesh/storage.py`)
- Persists alerts, reverse delivery receipts, node registries, and diagnostic test logs.
