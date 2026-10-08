# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **POWDER testbed profile** for 5G handover experiments with OCUDU and Open5GS on the conducted RF attenuator matrix. It is based on `https://gitlab.flux.utah.edu/dmaas/srs-rf-matrix`, with the N300 node turned into a second, separate gNB for inter-gNB handover. There is no O-RAN RIC or shared VLAN.

The entry point is [profile.py](profile.py). The previous LTE/srsRAN 4G profile is kept unchanged under [legacy-lte/](legacy-lte/) and is not used by the 5G profile.

## Platform Context

Experiments are instantiated via the [POWDER](https://powderwireless.net) portal, not run locally. The repo is checked out at `/local/repository` on every node; scripts in [bin/](bin/) run at boot or manually over SSH.

- **OS**: Ubuntu 22.04 (COTS UE image on the NUCs)
- **Build/config directory on nodes**: `/var/tmp` (OCUDU in `/var/tmp/ocudu`, gNB configs copied to `/var/tmp/etc/ocudu`)
- UHD 4.10 debs are vendored in [debs/](debs/)

## Topology

| Node | Hardware | Role |
|------|----------|------|
| `cn5g` | d430 | Open5GS core (192.168.1.1) |
| `cudu` | d740 + `x310-1` | gNB 1, gNB ID 411 (192.168.1.2) |
| `cudu2` | d740 + `n300-2` | gNB 2, gNB ID 412, PCI 3 (192.168.1.3) |
| `ue1`, `ue2` | `nuc27`, `nuc22` | Quectel RM520 COTS UEs |

RF paths in the matrix are fixed by POWDER staff; only attenuation values can be changed.

## gNB configs ([etc/ocudu/](etc/ocudu/))

- `gnb_rf_x310_ho.yml` — upstream intra-gNB handover: two cells (PCI 1, 2) on the X310
- `gnb1_rf_x310_inter_ho.yml`, `gnb2_rf_n300_inter_ho.yml` — inter-gNB handover (NG handover via the AMF). The `SSBARFCN` placeholder must be replaced with the `dl_ssb_arfcn` the gNB prints at startup.

Inter-gNB handover only works when forced from the gNB console (`ho <serving pci> <rnti> <target pci>`): the two radios get no PPS, so the cells are not time-aligned and the UE never reports the other cell. It also needs the OCUDU patch in [etc/ocudu-patches/](etc/ocudu-patches/), which `deploy-ocudu.sh` does not apply. Details and evidence are in [note/troubleshooting.md](note/troubleshooting.md) sections 6 and 7; the run sheet is [note/commands.md](note/commands.md).

## Key Scripts

| Script | Node | Purpose |
|--------|------|---------|
| [bin/deploy-open5gs.sh](bin/deploy-open5gs.sh) | cn5g | Install Open5GS, add the two subscribers |
| [bin/deploy-ocudu.sh](bin/deploy-ocudu.sh) | cudu, cudu2 | Build OCUDU, copy gNB configs |
| [bin/setup-cots-ue.sh](bin/setup-cots-ue.sh) | ue1, ue2 | Quectel modem setup |
| [bin/update-attens](bin/update-attens) | cudu, cudu2 | Set a path group (`ru1ue1`, `ru2ue1`, `gnb2ue1`, ...) to 0..95 (+30 dB) |
| [bin/start-inter-gnb](bin/start-inter-gnb) | cudu, cudu2 | Prepare the node's inter-gNB config and start its gNB |
| [bin/handover](bin/handover) | cudu | Fade a UE between the X310's two cells |
| [bin/handover-gnb](bin/handover-gnb) | cudu, cudu2 | Fade a UE between gNB 1 and gNB 2 (does not trigger a handover; see the note above) |
| [bin/meas-reports.py](bin/meas-reports.py) | cudu, cudu2 | Extract UE measurement reports from `/tmp/gnb.log` as CSV or JSON lines |
| [bin/ngap-capture](bin/ngap-capture) | cn5g | Capture NGAP (SCTP 38412) to a pcap |
| [bin/run-inter-gnb-exp](bin/run-inter-gnb-exp) | your machine | Whole inter-gNB handover run over SSH (hosts in `hosts.env`); results land in `traces/` |

Run attenuator commands on the server nodes, not the NUCs.
