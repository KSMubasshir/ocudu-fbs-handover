# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **POWDER testbed profile** for 5G handover experiments on the conducted RF attenuator matrix. It is based on `https://gitlab.flux.utah.edu/dmaas/srs-rf-matrix`, with the N300 node turned into a second, separate gNB for inter-gNB handover. There is no O-RAN RIC or shared VLAN.

On this branch (`oai-fbs`) both gNBs are **OpenAirInterface (OAI)** gNBs, each on its **own Open5GS core**, and gNB 2 is a **false base station (FBS)** per the NIST FBS white paper (CSWP 36G, [nis-fbs-white-paper.pdf](nis-fbs-white-paper.pdf)). gNB 1 on `cn5g` is the home network (PLMN 999/99, TAC 1); gNB 2 on `cn5g2` is the FBS: it **clones the home cell** -- same PLMN 999/99 and same carrier (3619.2 MHz, SSB ARFCN 641280) as gNB 1 -- but keeps its own PCI (3) and broadcasts a **different TAC (2)** on its own core 2, which holds the same subscribers. The UE registers on the home network and goes idle; when the FBS out-powers gNB 1 at the UE, the idle UE reselects to the FBS **intra-frequency** (a UE-autonomous idle procedure, so no SIB4 or measurement config is needed -- unlike connected-mode handover) and, finding a new TAI, performs **mobility registration on the FBS's core 2**. The SIM homed on 999/99 registers on the attacker's network -- the UE has been lured off the legitimate home network. Tested on the testbed via [bin/run-fbs-exp](bin/run-fbs-exp) (`-s lure`, the default; `traces/fbs-lure-*`): the idle UE moves from home PCI 1/TAC 1 to FBS PCI 3/TAC 2 (RSRP about -81 dBm) and core 2's AMF logs `Registration complete` -- the UE is lured onto the attacker network. Three **active-denial DoS scenarios** then build on that lure (`-s reject|drop_rrc|drop_nas`): the FBS answers the UE's RRCSetupRequest with RRCReject (scenario 2), ignores it (scenario 1), or completes RRC but drops the UE's NAS Registration Request (scenario 3). These need gNB 2 built with [patches/oai-fbs-misbehavior.patch](patches/oai-fbs-misbehavior.patch) (applied by `deploy-oai.sh`; `OAI_FBS_MODE` selects the behaviour at runtime, passed by `start-oai-gnb -m`). All three were confirmed on the testbed (`traces/fbs-{reject,drop_rrc,drop_nas}-*`): the UE repeatedly reaches the FBS and is denied service every time (scenario 3 gives up after exactly 5 NAS attempts, matching the paper), nothing reaches the FBS core, and the UE is left on an unusable faded home cell -- a DoS. The remaining white paper scenarios 4-6 (fake NAS Accept, fake/tampered NAS Reject) need core-side (AMF) changes and are not yet implemented.

The **failed-handover scenario** (gNB 2 as an unrelated network on a separate carrier / foreign PLMN, handover refused at the source for an unknown PCI) lives on its own branch, **`oai-failed-handover`**, so both scenarios stay reproducible. This branch derives from it; the OCUDU scripts/configs/notes from `optional-second-gnb` are still in the tree but unused.

The entry point is [profile.py](profile.py). The previous LTE/srsRAN 4G profile is kept unchanged under [legacy-lte/](legacy-lte/) and is not used by the 5G profile.

## Platform Context

Experiments are instantiated via the [POWDER](https://powderwireless.net) portal, not run locally. The repo is checked out at `/local/repository` on every node; scripts in [bin/](bin/) run at boot or manually over SSH.

- **OS**: Ubuntu 22.04 (COTS UE image on the NUCs)
- **Build/config directory on nodes**: `/var/tmp` (OAI in `/var/tmp/oai`, gNB configs copied to `/var/tmp/etc/oai`)
- UHD 4.10 debs are vendored in [debs/](debs/)

## Topology

| Node | Hardware | Role |
|------|----------|------|
| `cn5g` | d430 | Open5GS core 1, PLMN 999/99 (192.168.1.1) |
| `cudu` | d740 + `x310-1` | gNB 1 -> core 1, gNB ID 411, PCI 1 (192.168.1.2) |
| `cn5g2` | d430 | Open5GS core 2 (FBS core), PLMN 999/99, TAC 2 (192.168.1.4) |
| `cudu2` | d740 + `n300-2` | gNB 2 (FBS) -> core 2, gNB ID 412, PCI 3 (192.168.1.3) |
| `ue1`, `ue2` | `nuc27`, `nuc22` | Quectel RM520 COTS UEs (SIMs homed on 999/99) |

RF paths in the matrix are fixed by POWDER staff; only attenuation values can be changed.

## OAI gNB configs ([etc/oai/](etc/oai/))

- `gnb1_x310_core1.conf` — gNB 1, PLMN 999/99, AMF 192.168.1.1 (core 1).
- `gnb2_n300_core2.conf` — gNB 2, the **FBS**: PLMN **999/99** (same as home), carrier **641280** (same as home), PCI **3**, **TAC 2**, AMF **192.168.1.4** (core 2). Its NG/NGU interface is still the node's own 192.168.1.3.

Both are derived from OAI's `gnb.sa.band78.fr1.106PRB.pci0.rfsim.conf` (one band 78, 106 PRB cell each) and differ in gNB ID, `nr_cellid` (gNB ID * 256 + 1), PCI, PRACH root sequence and `ssb_PositionsInBurst_Bitmap`. For the FBS to clone the home cell, gNB 2 now shares gNB 1's carrier (641280 / Point A 640008) and PLMN (999/99); it differs only in cell identity (PCI 3, PRACH root, SSB bitmap), TAC (2) and the `RUs` section. The idle UE reselects to the stronger of the two SSBs on that carrier (intra-frequency), so no neighbour list or SIB4 is needed. Two pairs of values must agree: `plmn_list`/`tracking_area_code` in `gnb2_n300_core2.conf` and the `CORE2_MCC`/`CORE2_MNC`/`CORE2_TAC` constants in [profile.py](profile.py) that are passed to `deploy-open5gs.sh` on `cn5g2` (the AMF must serve gNB 2's TAC).

`bin/start-oai-gnb` adds the radio options: `-E --continuous-tx` on the X310 (46.08 Msps from its 184.32 MHz clock), none on the N300 (61.44 Msps from 122.88 MHz). Keep `time_src` internal: OAI blocks waiting for a PPS otherwise. `start-oai-gnb` also forces the node's 192.168.1.x interface to MTU 1500 (carried over from the handover branch, where a 9000 MTU silently dropped the oversized HandoverRequired; harmless here).

The OCUDU configs are in [etc/ocudu/](etc/ocudu/), their run sheet is [note/commands.md](note/commands.md).

## Key Scripts

| Script | Node | Purpose |
|--------|------|---------|
| [bin/deploy-open5gs.sh](bin/deploy-open5gs.sh) | cn5g, cn5g2 | Install Open5GS + subscribers; no args = core 1 (999/99), `<mcc> <mnc>` = a second core on another node (NGAP/N3 bound to the node's own 192.168.1.x) |
| [bin/deploy-oai.sh](bin/deploy-oai.sh) | cudu, cudu2 | Build OAI (gNB, USRP, telnet server), apply `patches/oai-fbs-misbehavior.patch`, copy gNB configs |
| [bin/setup-cots-ue.sh](bin/setup-cots-ue.sh) | ue1, ue2 | Quectel modem setup |
| [bin/update-attens](bin/update-attens) | cudu, cudu2 | Set a path group (`ru1ue1`, `ru2ue1`, `gnb2ue1`, ...) to 0..95 (+30 dB) |
| [bin/start-oai-gnb](bin/start-oai-gnb) | cudu, cudu2 | Start the node's OAI gNB (gNB 1 -> core 1, gNB 2 -> core 2); output to `/tmp/gnb.log`. `-m reject\|drop_rrc\|drop_nas` sets the FBS misbehaviour on gNB 2 (`OAI_FBS_MODE`) |
| [bin/handover-gnb](bin/handover-gnb) | cudu, cudu2 | Fade a UE between gNB 1 and gNB 2 (no handover here, just signal levels) |
| [bin/ngap-capture](bin/ngap-capture) | cn5g, cn5g2 | Capture that core's NGAP (SCTP 38412) to a pcap |
| [bin/oai-meas-log.py](bin/oai-meas-log.py) | cudu, cudu2 | Sample the UE measurement reports from OAI's `nrRRC_stats.log` as CSV (OAI does not log them) |
| [bin/run-fbs-exp](bin/run-fbs-exp) | your machine | Whole FBS run over SSH (hosts in `hosts.env`, needs `CN5G2`). `-s lure` (default): UE attaches to the home network, goes idle, the FBS out-powers it, and the idle UE reselects to the FBS (PCI 3/TAC 2) and registers on core 2. `-s reject\|drop_rrc\|drop_nas`: white paper DoS scenarios 2/1/3, the FBS denies service (needs the FBS patch on gNB 2). Captures both cores' NGAP from before the gNBs start, both AMF logs, both gNB logs, each gNB's UE measurement reports and the FBS's misbehaviour log; results in `traces/fbs-<scenario>-<date>-<time>` |
| [bin/run-failed-ho-exp](bin/run-failed-ho-exp) | your machine | Whole failed-handover run over SSH (hosts in `hosts.env`, needs `CN5G2`): start both gNBs, attach ue1, raise gNB 2, force gNB 1 toward gNB 2's unknown PCI, show gNB 1 refusing (no neighbour relation); captures both cores' NGAP from before the gNBs start, both AMF logs and each gNB's UE measurement reports (`gnb<n>-meas.csv`); results in `traces/failed-ho-<date>-<time>` |
| [bin/collect-node](bin/collect-node) | any node | Run on a node to bundle that node's own data (gNB log + RRC/MAC stats + config, or core AMF log + PLMN + NGAP pcap, or UE modem cells + ping) into a tarball in `/var/tmp`; for manual runs, since nodes cannot SSH to each other |
| [bin/run-second-core-exp](bin/run-second-core-exp) | your machine | Whole run over SSH (hosts in `hosts.env`, which needs `CN5G2` too): installs `etc/oai` configs, restarts both gNBs, attaches ue1 to gNB 1, then gNB 2 overpowers gNB 1 (gNB 1 untouched) with a modem scan, then a confirmed modem restart under the stronger foreign cell; results land in `traces/second-core-<date>-<time>` |

Run attenuator commands on the server nodes, not the NUCs. The OCUDU-only scripts (`deploy-ocudu.sh`, `start-inter-gnb`, `handover`, `meas-reports.py`, `run-inter-gnb-exp`, ...) are unused on this branch. The N2 handover helper (`n2-handover`) and whole-run script (`run-oai-n2-exp`) exist only on the `oai-n2-handover` branch, since this variant has no handover.
