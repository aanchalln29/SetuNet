# SETU-NET Product Requirements Document (PRD)

## 1. Executive Summary
SETU-NET is an application-layer emergency-alert system operating over phone-to-phone Wi-Fi Direct and Wi-Fi Aware ad-hoc connections to distribute priority-based disaster instructions and collect delivery acknowledgement reports without relying on cellular towers, mobile data, SIM cards, or external routers.

---

## 2. Problem Statement and User Personas (Slide 2)
During severe disasters, conventional commercial communications collapse due to tower destruction, electrical blackout, or severed backhaul.

### Target User Personas
1. The Affected Public (Civilians):
   - Needs: Immediate receipt of evacuation orders, rising water warnings, hazard boundary alerts.
   - Constraint: Disconnected phones with no cellular signal or mobile data.
2. First Responders and Search-and-Rescue (SAR) Teams:
   - Needs: Field-level situational awareness, patient triage notices, survivor extraction coordination.
   - Constraint: Operating in rubbled or remote sectors with no tower coverage.
3. Incident Commanders (EOC Controllers):
   - Needs: Verification of whether emergency broadcasts reached ground personnel (Acknowledgement reports).

---

## 3. Product Features and Functional Requirements (Slide 4, 6 & 7)

### 3.1 Four Priority Alert Categories
- Priority 0 (Critical / SOS): Life-threatening events. Preempts all queued alerts in every node.
- Priority 1 (Warning / Evacuation): Immediate area clearance instructions.
- Priority 2 (Tactical / Troop Movement): Tactical/patrol orders and team repositioning.
- Priority 3 (Informational / General): Status reports, shelter supplies, all-clear advisories.

### 3.2 Secure Multi-Hop Controlled Flooding
- Initial TTL: 6 hops (prevents runaway forwarding).
- Duplicate Suppression: LRU duplicate cache discards already-seen message IDs to prevent broadcast storms.
- Digital Signatures: Ed25519 asymmetric cryptography verifies message authenticity and prevents tampering.
- GPS Tagging: Every alert is stamped with latitude, longitude, and elevation.
- Time Offset Estimation: Pairwise two-way timestamp exchange normalizes clock drift between unsynchronized phones.

### 3.3 Reverse Acknowledgement (ACK) Reporting
- Each receiving device generates a signed delivery receipt.
- The receipt travels backwards along the hop path to the originating sender phone.
- Provides real-time delivery ratio (%) and per-hop latency metrics.

---

## 4. Performance Targets and Evaluation Criteria (Slide 5 & 8)

| Benchmark Metric | Design Target | Tested Prototype Performance |
|---|---|---|
| Transmission Range | 150m to 200m per hop (Open field) | Modeled & verified; attenuation in indoor mode |
| Per-Hop Latency | Less than 5.0 seconds per hop | Average 650ms to 1200ms per hop |
| Delivery Ratio | At least 90% across reachable nodes | 100% verified across reachable test rig nodes |
| Duplicate Elimination | 100% suppression of redundant copies | Verified via LRU sliding window cache |
| Network Scale | 8-phone baseline, 50-node logical target | Scalability verified up to 50 nodes |

---

## 5. System Deliverables and Roadmap (Slide 9 & 10)
- Deliverable 1: Native Android Application (Kotlin + Jetpack Compose).
- Deliverable 2: Reusable Mesh Relay Core Module (`src/mesh/`).
- Deliverable 3: Interactive Real-Time Operations and Monitoring Dashboard (`src/dashboard/`).
- Deliverable 4: Automated Verification Simulation Suite (`simulations/`).
- Deliverable 5: Standardized JSON Emergency Alert Wire Specification.

### Future Scope
- Hardware LoRa bridge nodes for long-distance inter-cluster relays (>5km).
- Satellite gateway uplink integration.
- Cross-platform iOS client.
- Vehicle-mounted mobile mesh relay nodes.
