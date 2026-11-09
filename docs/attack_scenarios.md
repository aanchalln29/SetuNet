# Attack Scenarios & Detection Results

PacketGuard ships a **synthetic, in-process** attack harness
([`simulations/`](../simulations/)). Each scenario fabricates a packet stream in
memory and feeds it to the detection engine to prove a rule fires. No scenario
touches a real network, needs root, or attacks any host — it is a reproducible
test bench, safe to run anywhere and in CI.

> In a real ethical-hacking lab you would reproduce these between isolated nodes
> with the tools named below, inside the sandboxed network defined in
> [`simulations/docker-compose.yml`](../simulations/docker-compose.yml). The
> harness is the deterministic equivalent for coursework.

Run everything:

```bash
python -m simulations.run_demo
```

Expected output: `11/11 checks passed` (baseline silence + chain integrity + the
nine attack scenarios below).

## Scenario matrix

| # | Scenario | Rule | Signal PacketGuard sees | Real-lab tool |
|---|----------|------|-------------------------|---------------|
| 1 | Packet tampering | **R002** | Received hash ≠ blockchain anchor | scapy payload edit |
| 2 | ARP spoof (MitM) | **R008** | Gateway IP's MAC changed from baseline | ettercap / arpspoof |
| 3 | Route hijack | **R007** | Flow TTL collapses (64 → 12) | route injection |
| 4 | Packet drop / theft | **R001** | Gap in the sender's sequence numbers | `iptables -j DROP` |
| 5 | Replay attack | **R003** | Authenticated payload re-sent under a new seq | scapy re-send |
| 6 | SYN flood (DoS) | **R004** | One IP exceeds the per-second rate threshold | `hping3 --flood -S` |
| 7 | Spam flood | **R005** | Same payload repeated many times in a window | bot script |
| 8 | Data exfiltration | **R006** | Large outbound burst to an external IP | bulk transfer |
| 9 | DNS tunneling | **R006** | Abnormally long DNS query name | iodine / dnscat2 |

Each scenario also has a standalone entry point, e.g.:

```bash
python -m simulations.mitm_attack      # R002 + R008
python -m simulations.packet_drop      # R001, with hop trace
python -m simulations.replay_attack    # R003
python -m simulations.syn_flood        # R004 + R005, with dry-run auto-fix
```

## What a detection looks like end-to-end

Taking **packet tampering (R002)** as the worked example:

1. The sender anchors the *legitimate* payload hash on the chain before sending.
2. The attacker alters the payload in transit (here: swapping an account number).
3. The receiver re-hashes what arrived; `verify_packet` returns `tampered`.
4. The engine builds a weakness report — suspect **Hop 3: 192.168.1.47**, ~95%
   confidence, likely **Man-in-the-Middle payload tampering**, weakness
   *"unencrypted segment permits payload modification in transit."*
5. The fix suggester returns: enable TLS/SSL on the segment, establish an IPSec
   tunnel, rotate keys — and composes a dry-run isolation command.
6. An alert is raised and appears on the dashboard with all of the above.

## Detection results (sample run)

From one `run_demo` pass (`difficulty=1`, fresh engine per scenario):

```
[PASS] Normal traffic           expected silence | fired: none
[PASS] Blockchain integrity     chain valid after 21 blocks
[PASS] Packet tampering (MitM)  expected R002 | fired: R002
[PASS] Packet drop / theft      expected R001 | fired: R001
[PASS] Replay attack            expected R003 | fired: R003
[PASS] SYN flood (DoS)          expected R004 | fired: R004
[PASS] Spam flood               expected R005 | fired: R005
[PASS] Data exfiltration        expected R006 | fired: R006
[PASS] DNS tunneling            expected R006 | fired: R006
[PASS] Route hijack (TTL)       expected R007 | fired: R007
[PASS] ARP spoof (MitM)         expected R008 | fired: R008
 11/11 checks passed
```

## Reproducing against a real lab (optional)

1. Bring up the sandboxed network: `docker compose -f simulations/docker-compose.yml up`.
   It is marked `internal: true` — **no route to your host or the internet.**
2. Run the real tools **only** from the monitored `attacker` node against the two
   lab nodes. Never against a network you do not own and have written permission
   to test.
3. Point the capture engine at the lab interface (`PacketSniffer(iface=...)`,
   requires root and scapy) and watch the same rules fire on real traffic.

See [`../PROJECT_PLAN.md` §11](../PROJECT_PLAN.md) for the full ethical/legal
rules. Short version: isolated lab only, no real user data, educational use.
