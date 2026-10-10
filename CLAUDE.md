# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **POWDER testbed profile** for 5G handover experiments on the conducted RF attenuator matrix. It is based on `https://gitlab.flux.utah.edu/dmaas/srs-rf-matrix`, with the N300 node turned into a second, separate gNB for inter-gNB handover. There is no O-RAN RIC or shared VLAN.

On this branch (`oai-n2-handover`) both gNBs are **OpenAirInterface (OAI)** gNBs and the profile follows the N2 handover section of OAI's [handover tutorial](https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/doc/handover-tutorial.md#n2-handover), with Open5GS as the core. The OCUDU scripts, configs and notes from the `optional-second-gnb` branch are still in the tree but [profile.py](profile.py) does not use them. The OAI setup has not been run on the testbed yet.

The entry point is [profile.py](profile.py). The previous LTE/srsRAN 4G profile is kept unchanged under [legacy-lte/](legacy-lte/) and is not used by the 5G profile.

## Platform Context

Experiments are instantiated via the [POWDER](https://powderwireless.net) portal, not run locally. The repo is checked out at `/local/repository` on every node; scripts in [bin/](bin/) run at boot or manually over SSH.

- **OS**: Ubuntu 22.04 (COTS UE image on the NUCs)
- **Build/config directory on nodes**: `/var/tmp` (OAI in `/var/tmp/oai`, gNB configs copied to `/var/tmp/etc/oai`)
- UHD 4.10 debs are vendored in [debs/](debs/)

## Topology

| Node | Hardware | Role |
|------|----------|------|
| `cn5g` | d430 | Open5GS core (192.168.1.1) |
| `cudu` | d740 + `x310-1` | gNB 1, gNB ID 411, PCI 1 (192.168.1.2) |
| `cudu2` | d740 + `n300-2` | gNB 2, gNB ID 412, PCI 3 (192.168.1.3) |
| `ue1`, `ue2` | `nuc27`, `nuc22` | Quectel RM520 COTS UEs |

RF paths in the matrix are fixed by POWDER staff; only attenuation values can be changed.

## OAI gNB configs ([etc/oai/](etc/oai/))

- `gnb1_x310_n2_ho.conf`, `gnb2_n300_n2_ho.conf` — one band 78, 106 PRB cell each on the same carrier, derived from OAI's `gnb.sa.band78.fr1.106PRB.pci0.rfsim.conf`. Apart from the header comment they differ only in gNB ID, `nr_cellid` (gNB ID * 256 + 1), PCI, PRACH root sequence, `ssb_PositionsInBurst_Bitmap`, N2/N3 address and the `RUs` section.
- `neighbour-config.conf` — neighbour list and measurement events, `@include`d by both.

`bin/start-oai-gnb` adds the radio options: `-E --continuous-tx` on the X310 (46.08 Msps from its 184.32 MHz clock), none on the N300 (61.44 Msps from 122.88 MHz). The handover is forced with `bin/n2-handover <target pci>` (telnet `ci trigger_n2_ho`); OAI also triggers it from an A3 report, but the two radios get no PPS, so the cells are not time-aligned and with OCUDU the UE never reported the other cell ([note/troubleshooting.md](note/troubleshooting.md) section 6). Keep `time_src` internal: OAI blocks waiting for a PPS otherwise.

The OCUDU configs are in [etc/ocudu/](etc/ocudu/), their run sheet is [note/commands.md](note/commands.md).

## Key Scripts

| Script | Node | Purpose |
|--------|------|---------|
| [bin/deploy-open5gs.sh](bin/deploy-open5gs.sh) | cn5g | Install Open5GS, add the two subscribers |
| [bin/deploy-oai.sh](bin/deploy-oai.sh) | cudu, cudu2 | Build OAI (gNB, USRP, telnet server), copy gNB configs |
| [bin/setup-cots-ue.sh](bin/setup-cots-ue.sh) | ue1, ue2 | Quectel modem setup |
| [bin/update-attens](bin/update-attens) | cudu, cudu2 | Set a path group (`ru1ue1`, `ru2ue1`, `gnb2ue1`, ...) to 0..95 (+30 dB) |
| [bin/start-oai-gnb](bin/start-oai-gnb) | cudu, cudu2 | Start the node's OAI gNB with the telnet server; output to `/tmp/gnb.log` |
| [bin/n2-handover](bin/n2-handover) | cudu, cudu2 | Force an N2 handover of a UE to the other gNB's PCI |
| [bin/handover-gnb](bin/handover-gnb) | cudu, cudu2 | Fade a UE between gNB 1 and gNB 2 (triggers a handover only if the UE reports the other cell; see the note above) |
| [bin/ngap-capture](bin/ngap-capture) | cn5g | Capture NGAP (SCTP 38412) to a pcap |

Run attenuator commands on the server nodes, not the NUCs. The OCUDU-only scripts (`deploy-ocudu.sh`, `start-inter-gnb`, `handover`, `meas-reports.py`, `run-inter-gnb-exp`, ...) are unused on this branch.
