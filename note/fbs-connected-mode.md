# FBS connected-mode findings

Companion to the idle lure (`note/commands.md`, `bin/run-fbs-exp`). Question:
a stronger FBS lures an **idle** UE by cell reselection -- does it also lure a
UE that is **RRC_CONNECTED** on the home network? Driver: `bin/run-fbs-connected-exp`.

## Headline result

**A connected UE does NOT follow a stronger FBS.** With the home cell trimmed so
the FBS (cloned cell, same carrier) was ~10 dB stronger at the UE, a connected
ue1 carrying a 4 Mbit/s downlink stayed on the home cell for the whole window,
kept zero packet loss, and never contacted the FBS. Nothing reached the FBS core.

Why: idle reselection is UE-autonomous, so a stronger FBS wins. Connected-mode
mobility is network-commanded -- the UE cannot leave on its own, and the home
gNB has no Xn/N2 neighbour relation (and no shared keys) to hand it to the FBS,
nor can the FBS forge an RRCReconfiguration the UE would accept. The connected
UE can only be moved by first being knocked offline (RLF), after which it drops
to idle and the ordinary idle lure applies.

## Runs (2026-10-15)

1. **fade home + ping** (`traces/fbs-connected-2026-10-15-155942`): UE stayed on
   home PCI 1, but was never actually connected -- the ping traffic generator
   failed to start and the modem stayed idle. Inconclusive.
2. **fade home + ping, fixed** (`traces/fbs-connected-2026-10-15-160645`): with
   the home cell faded to make the FBS stronger, the home link broke, the UE
   went idle and **reselected to the FBS, registering on core 2** -- i.e. the
   idle lure reproduced via radio-link failure, NOT a connected-mode result.
   Identical attenuation to run 1 gave the opposite outcome, confirming the UE
   was idle both times and the result was just nondeterministic idle reselection.
3. **TX-trim + iperf3** (`traces/fbs-connected-2026-10-15-190053`): the result
   above. Home trimmed 6 dB in config to ~-90 dBm, FBS at full power ~-80 dBm;
   UE held RRC_CONNECTED with a steady iperf3 downlink. UE stayed on home PCI 1,
   4 Mbit/s with 0/29674 datagrams lost, 202 home-gNB meas rows, 0 FBS accesses,
   0 FBS-core registrations.

## Method that works (and the two traps)

- **Do not fade the home matrix path to make the FBS stronger.** Because the FBS
  clones the home carrier, making it stronger means making home weaker, which
  breaks the home link and drops the UE to idle -- then it is the idle lure, not
  a connected-mode test. Instead lower the home gNB TX power in config
  (`att_tx`, the `-g` flag), keeping the home matrix path at 0 so the link stays
  clean while the FBS out-powers it. Too large a `-g` still breaks the home link
  via the FBS's co-channel interference, so keep the margin modest (6 dB worked).
- **The Quectel RM520 `QENG` servingcell "state" field is NOT a reliable RRC
  connection indicator.** It read `NOCONN` throughout run 3 even while the UE was
  receiving 4 Mbit/s with zero loss. Judge the connection from the network side
  instead: the home gNB logs measurements only for RRC_CONNECTED UEs (continuous
  "serving" rows in `home-meas.csv` = connected), plus the iperf3 loss figure.
  `bin/run-fbs-connected-exp` now decides the verdict from those, not from QENG.
- **Hold the connection with iperf3, not ping.** A light ping lets the gNB
  suspend the UE to RRC_INACTIVE; a continuous iperf3 downlink (server on ue1,
  client on the core) keeps it in RRC_CONNECTED.

## Reproduce

```
bin/run-fbs-connected-exp            # default: -g 6, phase 1 only, home kept up
bin/run-fbs-connected-exp -g 3       # less home trim if the link breaks under -g 6
bin/run-fbs-connected-exp -K         # also kill the home cell -> RLF -> idle lure
```

Needs all five nodes in `hosts.env` (incl. `CN5G2`), OAI built on cudu/cudu2,
Open5GS on cn5g (home) and cn5g2 (FBS core). iperf3 must be present on ue1 and
cn5g (it is on the current image).

## Open items

- The home gNB measurement config (`etc/oai/neighbour-config-measonly.conf`)
  still points at carrier 621312 (a failed-handover-branch leftover), not the
  FBS carrier 641280, so the UE is never asked to measure the FBS. The current
  result holds regardless (the UE stays because it is connected and the network
  has no path to the FBS), but a richer variant -- UE reports the stronger FBS
  PCI 3 and the home gNB refuses the handover -- needs an intra-frequency
  measurement config on 641280.
- Active connected-mode attacks from the literature (aLTEr / 5G relay) need a
  full transparent MitM relay (UE-side + gNB-side radio), which this two-gNB
  testbed does not provide; out of scope here.
