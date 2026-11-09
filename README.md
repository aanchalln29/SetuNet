# SETU-NET (सेतु-नेट)

> **Application-Layer Infrastructure-Independent Emergency Alert System over Phone-to-Phone Wi-Fi Mesh**  
> *Autonomous peer-to-peer communications protocol connecting populations and rescue units during conventional telecom collapse.*

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/Dependencies-Zero%20(Stdlib%20Only)-success)](https://github.com/aanchalln29/SetuNet)
[![Security](https://img.shields.io/badge/Security-Ed25519%20Signed-blueviolet)](https://github.com/aanchalln29/SetuNet)
[![Tests](https://img.shields.io/badge/Tests-71%20Passed-brightgreen)](https://github.com/aanchalln29/SetuNet)
[![Platform](https://img.shields.io/badge/Platform-Android%20%7C%20Linux%20%7C%20Windows-lightgrey)](https://github.com/aanchalln29/SetuNet)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

---

## 1. Problem Statement (Slide 2)

During natural and human-induced disasters (earthquakes, cyclones, flash floods, landslides), commercial telecommunication facilities frequently experience simultaneous systemic collapse:
- Cellular towers suffer physical damage, destruction, or severed backhaul connections.
- Power grids black out, exhausting base transceiver station battery banks within hours.
- Backhaul networks fail, preventing central emergency alerts (SMS, Cell Broadcast) from reaching the affected disaster perimeter.

This creates severe operational vulnerabilities:
- General Public: Evacuation directives and hazard zone warnings fail to reach populations at risk.
- Rescue Teams: First responders, medical personnel, and incident commanders face extreme coordination friction across adjacent sectors.
- Remote and Border Regions: Isolated groups remain severed from emergency command.

SETU-NET addresses the communications gap between individuals and response units who are physically close to one another (hundreds of meters apart) but cannot communicate due to the failure of intermediary infrastructure.

---

## 2. Existing Solutions and Research Gap (Slide 3)

| Technology | Strengths | Operational Failure Modes During Disasters |
|---|---|---|
| Cell Broadcast / SMS | Wide theoretical footprint | Complete dependency on operational telecom operators, electrical power, and intact backhaul. |
| Sirens & Fixed Radio | High acoustic coverage | One-way broadcast only; requires specialized stationary hardware; no delivery feedback. |
| Bluetooth Ad-Hoc | Direct peer-to-peer | Extremely limited physical range (10–15m); lacks alert prioritization, cryptographic integrity, and delivery reporting. |
| Wi-Fi Direct Multi-Hop | High throughput & range | Existing research demonstrates raw packet forwarding but lacks a unified framework combining **priority queuing, digital signatures, GPS tagging, and reverse delivery reports**. |

### The Research Gap
> To develop an application-layer emergency-alert system that sends priority-based alerts over phone-to-phone Wi-Fi connections and reports observed delivery back to the originating sender.

---

## 3. Proposed Architecture (Slide 4)

SETU-NET is designed as an autonomous Android application that allows nearby smartphones to exchange emergency directives without SIM cards, cellular connectivity, or external routers.

When an originating node generates an alert, it transmits directly to neighboring devices over Wi-Fi Direct or Wi-Fi Aware. Receiving devices verify packet integrity, insert the alert into an emergency priority queue, and forward it across multiple hops.

### Four Priority Alert Categories
1. Priority 0 (Critical / SOS): Life-threatening emergencies (structural collapse, victim triage). Preempts all queued lower-priority transmissions.
2. Priority 1 (Warning / Evacuation): Directives to evacuate an area (flood surge, fire perimeter).
3. Priority 2 (Tactical / Troop Movement): Controlled incident-command and responder unit repositioning.
4. Priority 3 (Informational / General): Operational status updates, supply confirmations, and all-clear advisories.

Every message encapsulates the alert priority type, GPS coordinates, local creation timestamp, Time-To-Live (initial TTL = 6), and an Ed25519 digital signature.

---

## 4. Quick Start (Zero Dependencies)

The engine, simulation harness, test suite, and operations dashboard operate exclusively on the Python standard library (Python 3.9+) with zero third-party package dependencies required.

```bash
# 1. Execute all 9 verification scenarios (tests flooding, preemption, TTL, Ed25519, ACKs, 50-node scale)
python -m simulations.run_demo

# 2. Launch the real-time Operations Dashboard and Topology Monitor
python -m src.dashboard.app

# Open in browser: http://127.0.0.1:8000

# 3. Execute the automated unit test suite (71 passing tests)
python -m unittest discover -s tests
```

---

## 5. System Objectives and Target Benchmarks (Slide 5)

| Metric | Target | Evaluation Status |
|---|---|---|
| Transmission Range | 150m to 200m per hop (Open ground) | Modeled with open-ground and indoor wall attenuation |
| Per-Hop Latency | Less than 5.0 seconds per hop | Observed empirical average: 650ms to 1200ms per hop |
| Delivery Ratio | At least 90% across reachable nodes | Verified: 100% across reachable baseline test-rig nodes |
| Scalability Target | 50 or more logical nodes | Verified in automated 50-node disaster cluster test |
| Loop Suppression | Controlled Flooding (TTL=6) + Duplicate Cache | Verified in simulation suite |
| Clock Synchronization | Pairwise time difference estimation | Verified via Cristian's algorithm offset filter |

---

## 6. The 8-Step System Methodology (Slide 6)

1. Step 1 (Trigger): An emergency responder or civilian initiates an alert.
2. Step 2 (Encoding): The application compiles the message with its priority type, GPS location, timestamp, and generates an Ed25519 digital signature over the canonical payload.
3. Step 3 (Peer Discovery): The device discovers neighboring nodes within 150m to 200m using Wi-Fi Direct or Wi-Fi Aware.
4. Step 4 (Transmission): The signed packet is transmitted to all active direct peer connections.
5. Step 5 (Duplicate Check): Receiving devices query their internal Duplicate Cache. If the message was already seen, the duplicate is dropped immediately, preventing broadcast storms.
6. Step 6 (Priority Enqueueing): Fresh alerts enter the PriorityMeshQueue. Priority 0 SOS alerts jump directly ahead of queued lower-priority alerts.
7. Step 7 (TTL Forwarding): The TTL is decremented by 1. If TTL reaches 0, forwarding ceases. If TTL > 0, the alert is forwarded to neighboring peers.
8. Step 8 (Delivery, Persistence & ACK): The device displays the alert, sounds the alarm, writes the record to SQLite, and transmits an Acknowledgement (ACK) packet back along the reverse hop path.

---

## 7. Implementation Architecture (Slide 7)

- Client Platform: Android application implemented in Kotlin and Jetpack Compose (`android/app/`).
- Transport Protocols: Wi-Fi Direct (`WifiP2pManager`), Wi-Fi Aware, and Google Nearby Connections.
- Mesh Logic Engine:
  - Priority Flooding: Expedites high-priority packets.
  - TTL-Based Limitation: Initial TTL = 6; halts propagation at TTL = 0.
  - Duplicate Cache: LRU cache with sliding timestamp window.
  - Local Storage: Android Room / SQLite database storing alert logs, reverse ACKs, and test telemetry.
- Cryptographic Verification: Asymmetric Ed25519 digital signatures ensure authenticity and tamper rejection; optional AES-GCM payload encryption.
- Test Rig: 8-phone configuration (1 Origin Sender, Relays 2–7, and 1 Out-of-Range Control Device Phone 8).

---

## 8. Measured Performance Metrics (Slide 8)

The prototype measures six core evaluation metrics:
1. Delivery Ratio (%): Proportion of reachable mesh nodes that received and acknowledged the alert.
2. Per-Hop Latency (ms): Transit delay between adjacent phone hops.
3. End-to-End Latency (ms): Total transmission duration from origin to boundary nodes.
4. Duplicate Count: Redundant broadcast copies suppressed by the duplicate filter.
5. Battery Consumption (mAh): Energy model tracking RF scanning, broadcast, reception, and listening states.
6. Acknowledged Nodes Count: Number of relay devices reporting reverse delivery receipts.

---

## 9. Deliverables and Future Scope (Slide 9 & 10)

- Deliverables:
  - Android application client with emergency UI.
  - Reusable mesh relay core module (`src/mesh/`).
  - Standardized JSON emergency alert format specification.
  - Automated verification simulation suite (`simulations/`).
  - Emergency dispatch and topology dashboard (`src/dashboard/`).
- Future Scope:
  - Long-range LoRa bridge nodes for multi-kilometer inter-cluster links.
  - Satellite gateway uplink integration for external incident command reporting.
  - iOS client implementation.
  - Vehicle-mounted mobile mesh repeaters.
- Environmental Limitation: Wi-Fi signal attenuates through concrete and rubble. When disconnected, nodes buffer alerts in local memory (Store-and-Carry) until physical motion restores proximity.

SETU-NET serves as a decentralized backup communication channel, complementing official civil emergency systems such as SACHET.
