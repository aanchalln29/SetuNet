# PacketGuard — Live Demo Walkthrough

A slide-by-slide map from the presentation narration to exactly what the running
prototype shows. Start the dashboard first:

```bash
cd "Cyber Project ATG" && export PYTHONPATH="$PWD"
python3 -m src.dashboard.app          # open http://127.0.0.1:8000
```

The demo driver fills the dashboard with live traffic immediately, and the
**Simulate attack** chips let you trigger each threat on cue.

---

## Slide 1 — What is PacketGuard & why not a vulnerability scanner

Nothing to click — this is the framing. Point at the **Live traffic** panel while
you say it: these are packets *in motion*, each verified against the ledger as it
arrives. Contrast with scanners (Nessus/OpenVAS/Nmap) that only inspect hosts *at
rest*. Call out the motivating case: industrial protocols like **Modbus** have no
built-in encryption and can't be patched, so integrity has to be checked on the
wire — which is what every row in that feed is doing.

## Slide 2 — How it works & why a blockchain

Point at the **Blockchain ledger** and **Witness quorum** panels.

1. The **three steps** (hash → anchor → re-check) are the feed's green "verified"
   rows: the sender anchored a SHA-256 hash, the receiver recomputed it and matched.
2. **Why blockchain, not a database:** the ledger panel shows hash-linked blocks.
3. **2-of-3 quorum — the headline.** Click **“Compromise a witness.”** It forges
   one witness node's copy of a recent packet. Watch:
   - the **Quorum** pill stays green and reads *“2/3”*,
   - witness **W3** flips to **compromised**,
   - the detail line reads *“Quorum intact (2/3); W3 compromised but outvoted.”*

   That is the live proof of the claim: a single compromised node cannot rewrite
   history, because the other two outvote it.

## Slide 3 — System architecture (four layers)

Walk the dashboard top to bottom — it mirrors the four layers:

| Layer | On screen |
|-------|-----------|
| Capture | the **Live traffic** feed (normalized src/dst/seq/hash rows) |
| Integrity | **Blockchain ledger** — note each block says **“8 pkts”**: that's Merkle **batching**, one block per 8 packets. Verification is still an O(1) hash lookup. |
| Detection | **Alerts** + **Attack distribution** (the 8 rules) |
| Response | each alert's suspect hop, fix list, and dry-run firewall command |

Mention it's all **standard-library Python** — no heavy installs.

## Slide 4 — What threats does it catch

Open the **Attack distribution** panel, then trigger a few chips live:

- **Four ledger-enabled** (`class: blockchain` in `rules.json`): **Tampering**
  (R002), **Packet theft/loss** (R001), **Replay** (R003), **Route hijack** (R007).
  Click **Tampering** and **Packet drop** — alerts fire instantly.
- **Four network-hygiene** (`class: hygiene`): **DoS flood** (R004), **Spam**
  (R005), **DNS tunneling / exfiltration** (R006), **ARP spoof** (R008).

Then open any alert to show the **Hop Tracer** output: it names the exact suspect
router (e.g. *Hop 3: 192.168.1.47*) with a confidence score and a ready-to-run
`iptables` command, kept in **dry-run** so an admin reviews before applying.

## Slide 5 — Working prototype & live demo

1. **41+ passing tests** (now 53): `python3 -m unittest discover -s tests`.
2. **Live dashboard** — already on screen: real-time traffic, growing blocks,
   live alerts.
3. **Attack simulation panel** — the chips you've been clicking.
4. **Cryptographic proof export (for audits).** In the **Incident proof** panel,
   type a sequence number from the feed (or click **proof ⤓** on any alert) and
   hit **Export proof.** It returns a self-verifying bundle: the anchored hash, the
   **Merkle audit path** (with a self-check), the block it lives in, chain
   validity, and each **witness's vote**. **Download JSON** saves it for the audit
   trail. This is the "exactly what happened to the data" artifact.

Closing line: *vulnerability scanners tell you if your servers have open doors;
PacketGuard makes sure nobody tampers with the packages moving between them.*

---

### One-command fallback (no dashboard)

If you can't show the browser, run the headless proof instead:

```bash
python3 -m simulations.run_demo     # 11/11 checks: every rule fires + chain intact
```
