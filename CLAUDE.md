# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **POWDER testbed profile** for 5G handover experiments on the conducted RF attenuator matrix. It is based on `https://gitlab.flux.utah.edu/dmaas/srs-rf-matrix`, with the N300 node turned into a second, separate gNB for inter-gNB handover. There is no O-RAN RIC or shared VLAN.

On this branch (`oai-failed-handover`) both gNBs are **OpenAirInterface (OAI)** gNBs, each on its **own Open5GS core**: gNB 1 on `cn5g` (home PLMN 999/99) and gNB 2 on `cn5g2` (foreign PLMN 001/01), on separate carriers (gNB 1 3619.2 MHz, gNB 2 3319.68 MHz). It extends `oai-second-core` with a **failed-handover scenario** modelled as an *unknown cell* (the spec-realistic case, TS 38.300): gNB 1 is configured to measure gNB 2's carrier via a measure-only neighbour config ([etc/oai/neighbour-config-measonly.conf](etc/oai/neighbour-config-measonly.conf)) so gNB 2 is a handover candidate, but gNB 1 holds **no neighbour relation (NCRT entry) for gNB 2's PCI (3)** -- only a legitimate same-operator sister cell on that frequency (PCI 500, not on air). When the UE reports gNB 2, gNB 1 cannot resolve the PCI to a target NCGI and refuses the handover at the source (OAI has no `reportCGI` fallback); nothing is sent to the core. gNB 1 and core 1 hold no information about gNB 2 or core 2. Tested on the testbed on 2026-10-10 (`traces/failed-ho-*`): forcing a handover toward PCI 3 yields `could not find neighbour cell with PCI=3`, no NGAP `HandoverRequired`, and the UE stays on gNB 1 (999/99, PCI 1), ping uninterrupted. The UE does **not** spontaneously report gNB 2 on this testbed (empty neighbour-cell list, no measurement report; no PPS, COTS modem), so the handover is forced from gNB 1's telnet console (`ci trigger_n2_ho 3,<ue>`) as a stand-in for the UE's request; the outcome (unknown PCI -> refused) is the same either way. It derives from the `oai-n2-handover` branch (tested N2 handover with one shared core); the OCUDU scripts/configs/notes from `optional-second-gnb` are still in the tree but unused.

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
| `cn5g2` | d430 | Open5GS core 2, PLMN 001/01 (192.168.1.4) |
| `cudu2` | d740 + `n300-2` | gNB 2 -> core 2, gNB ID 412, PCI 3 (192.168.1.3) |
| `ue1`, `ue2` | `nuc27`, `nuc22` | Quectel RM520 COTS UEs (SIMs homed on 999/99) |

RF paths in the matrix are fixed by POWDER staff; only attenuation values can be changed.

## OAI gNB configs ([etc/oai/](etc/oai/))

- `gnb1_x310_core1.conf` — gNB 1, PLMN 999/99, AMF 192.168.1.1 (core 1).
- `gnb2_n300_core2.conf` — gNB 2, PLMN **001/01**, AMF **192.168.1.4** (core 2). Its NG/NGU interface is still the node's own 192.168.1.3.

Both are derived from OAI's `gnb.sa.band78.fr1.106PRB.pci0.rfsim.conf` (one band 78, 106 PRB cell each) and differ in gNB ID, `nr_cellid` (gNB ID * 256 + 1), PCI, PRACH root sequence, `ssb_PositionsInBurst_Bitmap`, PLMN, AMF address and the `RUs` section. gNB 2 is on its own carrier (SSB ARFCN 621312 / Point A 620040, about 3.32 GHz, from OAI's stock `pci1` config) instead of gNB 1's 641280 / 640008: on a shared carrier the two cells are not time aligned and the modem's `AT+QSCAN` only ever listed one of them. Neither includes a neighbour list: there is no handover on this branch. The foreign PLMN lives in two places that must agree — `plmn_list` in `gnb2_n300_core2.conf` and the `FOREIGN_MCC`/`FOREIGN_MNC` constants in [profile.py](profile.py) that are passed to `deploy-open5gs.sh` on `cn5g2`.

`bin/start-oai-gnb` adds the radio options: `-E --continuous-tx` on the X310 (46.08 Msps from its 184.32 MHz clock), none on the N300 (61.44 Msps from 122.88 MHz). Keep `time_src` internal: OAI blocks waiting for a PPS otherwise. `start-oai-gnb` also forces the node's 192.168.1.x interface to MTU 1500 (carried over from the handover branch, where a 9000 MTU silently dropped the oversized HandoverRequired; harmless here).

The OCUDU configs are in [etc/ocudu/](etc/ocudu/), their run sheet is [note/commands.md](note/commands.md).

## Key Scripts

| Script | Node | Purpose |
|--------|------|---------|
| [bin/deploy-open5gs.sh](bin/deploy-open5gs.sh) | cn5g, cn5g2 | Install Open5GS + subscribers; no args = core 1 (999/99), `<mcc> <mnc>` = a second core on another node (NGAP/N3 bound to the node's own 192.168.1.x) |
| [bin/deploy-oai.sh](bin/deploy-oai.sh) | cudu, cudu2 | Build OAI (gNB, USRP, telnet server), copy gNB configs |
| [bin/setup-cots-ue.sh](bin/setup-cots-ue.sh) | ue1, ue2 | Quectel modem setup |
| [bin/update-attens](bin/update-attens) | cudu, cudu2 | Set a path group (`ru1ue1`, `ru2ue1`, `gnb2ue1`, ...) to 0..95 (+30 dB) |
| [bin/start-oai-gnb](bin/start-oai-gnb) | cudu, cudu2 | Start the node's OAI gNB (gNB 1 -> core 1, gNB 2 -> core 2); output to `/tmp/gnb.log` |
| [bin/handover-gnb](bin/handover-gnb) | cudu, cudu2 | Fade a UE between gNB 1 and gNB 2 (no handover here, just signal levels) |
| [bin/ngap-capture](bin/ngap-capture) | cn5g, cn5g2 | Capture that core's NGAP (SCTP 38412) to a pcap |
| [bin/oai-meas-log.py](bin/oai-meas-log.py) | cudu, cudu2 | Sample the UE measurement reports from OAI's `nrRRC_stats.log` as CSV (OAI does not log them) |
| [bin/run-failed-ho-exp](bin/run-failed-ho-exp) | your machine | Whole failed-handover run over SSH (hosts in `hosts.env`, needs `CN5G2`): start both gNBs, attach ue1, raise gNB 2, force gNB 1 toward gNB 2's unknown PCI, show gNB 1 refusing (no neighbour relation); results in `traces/failed-ho-<date>-<time>` |
| [bin/collect-node](bin/collect-node) | any node | Run on a node to bundle that node's own data (gNB log + RRC/MAC stats + config, or core AMF log + PLMN + NGAP pcap, or UE modem cells + ping) into a tarball in `/var/tmp`; for manual runs, since nodes cannot SSH to each other |
| [bin/run-second-core-exp](bin/run-second-core-exp) | your machine | Whole run over SSH (hosts in `hosts.env`, which needs `CN5G2` too): installs `etc/oai` configs, restarts both gNBs, attaches ue1 to gNB 1, then gNB 2 overpowers gNB 1 (gNB 1 untouched) with a modem scan, then a confirmed modem restart under the stronger foreign cell; results land in `traces/second-core-<date>-<time>` |

Run attenuator commands on the server nodes, not the NUCs. The OCUDU-only scripts (`deploy-ocudu.sh`, `start-inter-gnb`, `handover`, `meas-reports.py`, `run-inter-gnb-exp`, ...) are unused on this branch. The N2 handover helper (`n2-handover`) and whole-run script (`run-oai-n2-exp`) exist only on the `oai-n2-handover` branch, since this variant has no handover.
