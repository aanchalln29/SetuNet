# SETU-NET Engineering Project Plan and Technical Brief

> **Project Title:** SETU-NET: Application-Layer Multi-Hop Emergency Alert System over Phone-to-Phone Wi-Fi  
> **Course / Context:** Wireless Ad-Hoc Networks, Mobile Mesh & Disaster Communication Systems  

---

## 1. Project Overview & Motivation
Natural disasters systematically dismantle conventional telecom infrastructure. Cellular base stations require power grids and backhaul fiber; when either fails, central alerts (SMS, cell broadcast) fail to reach the population.

SETU-NET establishes an infrastructure-free, application-layer mesh network using smartphones' built-in Wi-Fi Direct and Wi-Fi Aware radios. It implements **controlled flooding**, **strict priority queuing**, **Ed25519 digital signatures**, **GPS tagging**, and **reverse delivery acknowledgement (ACK) reporting**.

---

## 2. Research Gap Analysis (Slide 3)
1. **Cellular Broadcast & SMS:** Fails upon infrastructure collapse.
2. **Sirens & Radio:** One-way, static, lack acknowledgement receipts.
3. **Bluetooth Meshes:** Extremely short physical range (10–15m), lacks priority queues and delivery reports.
4. **Existing Wi-Fi P2P Literature:** Explored ad-hoc data forwarding, but has **not combined priority-based preemption, cryptographic integrity signatures, GPS tagging, and reverse delivery reports**.

---

## 3. The 8-Step Operational Workflow (Slide 6)

1. **Step 1 — Alert Trigger:** User or emergency responder selects an alert category (SOS, Evacuation, Troop Movement, General) and enters instructions.
2. **Step 2 — Cryptographic Encoding:** The application constructs the message with category, GPS coordinates, local timestamp, and signs the canonical payload using **Ed25519**.
3. **Step 3 — Peer Discovery:** Nearby devices are discovered via Wi-Fi Direct P2P discovery / Wi-Fi Aware.
4. **Step 4 — Direct Transmission:** The signed packet is transmitted to all active direct peer connections.
5. **Step 5 — Duplicate Check:** Receiving phones check their internal **Duplicate Cache**. If the message ID was already processed, the packet is discarded immediately.
6. **Step 6 — Priority Enqueueing:** Fresh packets are placed in the **PriorityMeshQueue**. SOS alerts preempt lower-priority messages and jump to the queue head.
7. **Step 7 — TTL Hop Decrement:** The packet's TTL is decremented by 1 (initial TTL = 6). If TTL reaches 0, forwarding terminates; otherwise, it is broadcast to the next hop ring.
8. **Step 8 — Alert Delivery & ACK:** The receiving phone sounds the emergency alarm, logs the alert to local SQLite, and sends a reverse **Acknowledgement (ACK)** packet back to the origin sender.

---

## 4. Test Rig Configuration (Slide 5 & 7)

The baseline experimental evaluation utilizes an 8-phone configuration:
- **Phone 1 (Sender / EOC Station):** Initiates broadcasts and collects reverse delivery reports.
- **Phones 2 through 7 (Relay Devices):** Positioned along a progressive multi-hop line (120m to 140m spacing).
- **Phone 8 (Control Device):** Positioned at ~3,900m to establish an out-of-range baseline and evaluate Store-and-Carry buffering.

---

## 5. Verification Scenarios & Acceptance Criteria

| Scenario | Objective | Target | Status |
|---|---|---|---|
| `scenario_normal_multihop` | 8-phone multi-hop flooding | &ge; 90% delivery, < 5s per hop | Verified (100% reachable) |
| `scenario_sos_preemption` | SOS preemption over queue | SOS at queue head | Verified |
| `scenario_duplicate_suppression` | Storm & loop elimination | Duplicates discarded | Verified |
| `scenario_ttl_expiration` | Hop limit termination | Drops at TTL=0 | Verified |
| `scenario_tampered_signature` | Cryptographic integrity | Rejects forged signatures | Verified |
| `scenario_ack_roundtrip` | Reverse delivery trace | Origin receives ACKs | Verified |
| `scenario_sparse_network` | Store-and-carry buffer | Out-of-range buffering | Verified |
| `scenario_clock_skew` | Clock synchronization | Estimated offset accuracy | Verified |
| `scenario_scalability_50_nodes` | Large-scale scalability | &ge; 40/50 nodes reached | Verified |
