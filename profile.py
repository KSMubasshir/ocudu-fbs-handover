#!/usr/bin/env python

# POWDER profile for the 4G (LTE) false base station experiments: the LTE twin
# of the 5G FBS profile (the root profile.py on the oai-fbs branch). It mirrors
# that topology exactly -- two independent cores, a home eNB and an FBS eNB on
# the X310 and
# N300, two COTS UE NUCs, and the programmable attenuator matrix -- but runs an
# LTE stack (OAI lte-softmodem + Open5GS in EPC mode) so the same idle-lure and
# connected-mode tests can be run against LTE and compared with 5G.
#
# Why this layout and not the legacy srsRAN handover profile (legacy-lte/): the
# FBS findings depend on real COTS modem behaviour (idle reselection, QENG,
# connected-mode), two separate cores holding the same subscribers on different
# TACs (so the lure triggers mobility/TAU on the attacker core), and the
# conducted attenuator matrix. A software srsUE on a NUC+B210 with one shared
# srsEPC cannot reproduce those, so this profile reuses the 5G FBS hardware and
# matrix and only swaps the radio-access and core software for LTE.

import os

import geni.portal as portal
import geni.rspec.pg as pg
import geni.rspec.igext as ig
import geni.rspec.emulab.pnext as pn
import geni.rspec.emulab as emulab


tourDescription = """
### OAI 4G/LTE: a false base station on its own EPC (LTE twin of the 5G FBS profile)

This profile instantiates two independent OpenAirInterface (OAI) LTE networks on POWDER in a conducted RF environment with programmable attenuators. eNB 2 is **not** attached to the same core as eNB 1; it has its own Open5GS EPC and is the **false base station (FBS)**. It clones eNB 1's carrier (same EARFCN) and PLMN but keeps its own physical cell identity and broadcasts a **different TAC** on its own EPC, which holds the same subscribers.

The following will be deployed:
- Open5GS EPC 1 (`epc`, Dell R430), home PLMN 999/99, TAC 1 (192.168.1.1)
- OAI eNB 1 (`enb1`, Dell R740 + USRP X310) -> EPC 1 (192.168.1.2), the home cell
- Open5GS EPC 2 (`epc2`, Dell R430), same PLMN 999/99, TAC 2 (192.168.1.4), the FBS core
- OAI eNB 2 (`enb2`, Dell R740 + USRP N300) -> EPC 2 (192.168.1.3), the false base station
- 2 Intel NUCs w/ Quectel RM520 COTS UEs (the RM520 is 4G/5G; here it runs in LTE)

With eNB 2 shielded the UE attaches on eNB 1 / EPC 1 (home); when eNB 2 out-powers eNB 1 at an idle UE, the UE reselects to the FBS and, finding a new TAC, performs a Tracking Area Update / attach on EPC 2. The connected-mode counterpart (does a UE connected on eNB 1 follow a stronger FBS?) mirrors the 5G `bin/run-fbs-connected-exp`.

#### Measurements and observation points

- **Programmable attenuator matrix**: `bin/atten -l` lists the RF paths, `bin/update-attens <group> <0..95>` sets a eNB/UE pair (actual attenuation is 30 + value dB; `ru1ue1`/`ru1ue2` are eNB 1, `gnb2ue1`/`gnb2ue2` are eNB 2). Run on `enb1` or `enb2`, not the NUCs.
- **eNB output and log**: `start-oai-enb` writes `lte-softmodem` output to `/tmp/enb.log`.
- **COTS UE serving cell and RF readings** (on `ue1`/`ue2`): the same Quectel tooling as the 5G profile (`bin/ue_metrics.py`, `bin/quectel_control.py scan`), reporting the LTE serving cell, EARFCN, PCI, TAC, RSRP/RSRQ/SINR.
- **Both cores**: Open5GS MME logs via `journalctl` on `epc` and `epc2`; an S1AP capture (SCTP 36412) on either.
- **End-to-end traffic**: `ping`/`iperf3` between the UE and its EPC's SGW-U/PGW-U.
"""

tourInstructions = """

Startup scripts will still be running when the experiment becomes ready. Wait until all compute nodes show "Finished" in the List View (the OAI build takes a while).

Monitor each EPC's MME:

```
# on the epc node (home, PLMN 999/99, TAC 1)
sudo journalctl -u open5gs-mmed -f --output cat

# on the epc2 node (FBS core, PLMN 999/99, TAC 2)
sudo journalctl -u open5gs-mmed -f --output cat
```

Start one eNB on each eNB node (eNB 1 -> EPC 1 on `enb1`, eNB 2 -> EPC 2 on `enb2`):

```
# on enb1 (home, X310)
/local/repository/bin/start-oai-enb

# on enb2 (FBS, N300)
/local/repository/bin/start-oai-enb
```

Each eNB should complete S1 Setup in its EPC's MME log. Attach ue1 on the home network (this profile initializes the attenuators so eNB 1 <-> ue1 has minimum attenuation and all other paths maximum), then raise the FBS at the UE and run the lure / connected-mode scripts under `bin/`.

Notes: the LTE band / EARFCN, PLMN and TAC are set in the eNB configs under `etc/oai-lte/` (eNB broadcast) and passed to the EPC deploy script for `epc2` (core); change them together. The radio gains (`att_tx`, `att_rx`, `max_rxgain`) are OAI's stock values per radio and may need tuning, exactly as in the 5G profile.
"""

BIN_PATH = "/local/repository/bin"
ETC_PATH = "/local/repository/etc"
UBUNTU_IMG = "urn:publicid:IDN+emulab.net+image+emulab-ops//UBUNTU22-64-STD"
COTS_UE_IMG = "urn:publicid:IDN+emulab.net+image+PowderTeam:cots-jammy-image"
COMP_MANAGER_ID = "urn:publicid:IDN+emulab.net+authority+cm"
# OAI develop as of 2026-10-04 (same checkout as the 5G profile; the LTE configs
# in etc/oai-lte are derived from the reference eNB configs of this revision).
DEFAULT_OAI_HASH = "f8f769592a7030be88ede4bb5ca66fa1ca6a80e0"
# Open5GS in EPC mode (MME/SGW-C/SGW-U/PGW-C.../HSS); no args = home EPC 1
# (999/99, TAC 1), "<mcc> <mnc> <tac>" = a second EPC on another node.
EPC_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-open5gs-epc.sh")
# Builds OAI lte-softmodem (and applies the LTE FBS misbehaviour patch when
# present), then copies the eNB configs; mirrors deploy-oai.sh for 4G.
OAI_LTE_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-oai-lte.sh")
# PLMN/TAC broadcast by eNB 2 and its own core (epc2): same 999/99 as EPC 1 but
# a DIFFERENT TAC, so an idle UE that reselects to the FBS performs a TAU/attach
# on EPC 2. Must match the plmn/tac in etc/oai-lte/enb2_n300_epc2.conf.
CORE2_MCC = "999"
CORE2_MNC = "99"
CORE2_TAC = "2"
NODE_IDS = {
    "sdru": "x310-1",
    "sdru2": "n300-2",
    "ue1": "nuc27",
    "ue2": "nuc22",
}
MATRIX_GRAPH = {
    "sdru": ["ue1", "ue2"],
    "sdru2": ["ue1", "ue2"],
    "ue1": ["sdru", "sdru2"],
    "ue2": ["sdru", "sdru2"],
}
MATRIX_INPUTS = ["sdru", "sdru2"]

pc = portal.Context()
node_types = [
    ("d430", "Emulab, d430"),
    ("d740", "Emulab, d740"),
    ("d760p", "Emulab, d760"),
    ("d760-gpu", "Emulab, d760 w/ GPU"),
]
pc.defineParameter(
    name="sdru_nodetype",
    description="Type of compute node paired with the home eNB SDR",
    typ=portal.ParameterType.STRING,
    defaultValue=node_types[1],
    legalValues=node_types
)

pc.defineParameter(
    name="sdru2_nodetype",
    description="Type of compute node paired with the FBS eNB SDR",
    typ=portal.ParameterType.STRING,
    defaultValue=node_types[1],
    legalValues=node_types
)

pc.defineParameter(
    name="cn_nodetype",
    description="Type of compute node to use for each EPC node",
    typ=portal.ParameterType.STRING,
    defaultValue=node_types[0],
    legalValues=node_types
)

pc.defineParameter(
    name="sdr_compute_image",
    description="Image to use for compute connected to SDRs",
    typ=portal.ParameterType.STRING,
    defaultValue="",
    advanced=True
)

pc.defineParameter(
    name="oai_commit_hash",
    description="Commit hash, branch or tag for OAI (openairinterface5g; also builds lte-softmodem)",
    typ=portal.ParameterType.STRING,
    defaultValue="",
    advanced=True
)

params = pc.bindParameters()
pc.verifyParameters()

RF_IFACES = {}
RF_LINK_NAMES = {}
for k, v in MATRIX_GRAPH.items():
    RF_IFACES[k] = {}
    for node in (v):
        RF_IFACES[k][node] = "{}_{}_rf".format(k, node)
        if k in MATRIX_INPUTS:
            RF_LINK_NAMES["rflink_{}_{}".format(k, node)] = []

for k, v in MATRIX_GRAPH.items():
    if k in MATRIX_INPUTS:
        for node in (v):
            RF_LINK_NAMES["rflink_{}_{}".format(k, node)].append(RF_IFACES[k][node])
            RF_LINK_NAMES["rflink_{}_{}".format(k, node)].append(RF_IFACES[node][k])

request = pc.makeRequestRSpec()

# Home EPC (Open5GS EPC mode), 999/99 TAC 1.
role = "epc"
cn_node = request.RawPC(role)
cn_node.component_manager_id = COMP_MANAGER_ID
cn_node.hardware_type = params.cn_nodetype
cn_node.disk_image = UBUNTU_IMG
cn_if = cn_node.addInterface("{}-if".format(role))
cn_if.addAddress(pg.IPv4Address("192.168.1.1", "255.255.255.0"))
cn_link = request.Link("{}-link".format(role))
cn_link.setNoBandwidthShaping()
cn_link.addInterface(cn_if)
cn_node.addService(pg.Execute(shell="bash", command=EPC_DEPLOY_SCRIPT))

# FBS EPC: its own Open5GS EPC, same PLMN as EPC 1 but a different TAC. The
# deploy script binds S1AP/S1-U to this node's 192.168.1.4 and provisions the
# same subscribers under CORE2_MCC/CORE2_MNC.
role = "epc2"
cn2_node = request.RawPC(role)
cn2_node.component_manager_id = COMP_MANAGER_ID
cn2_node.hardware_type = params.cn_nodetype
cn2_node.disk_image = UBUNTU_IMG
cn2_if = cn2_node.addInterface("{}-if".format(role))
cn2_if.addAddress(pg.IPv4Address("192.168.1.4", "255.255.255.0"))
cn_link.addInterface(cn2_if)
cn2_cmd = "{} {} {} {}".format(EPC_DEPLOY_SCRIPT, CORE2_MCC, CORE2_MNC, CORE2_TAC)
cn2_node.addService(pg.Execute(shell="bash", command=cn2_cmd))

# collect node objects for RF matrix
matrix_nodes = {}

if params.oai_commit_hash:
    oai_hash = params.oai_commit_hash
else:
    oai_hash = DEFAULT_OAI_HASH
enb_build_cmd = "{} '{}'".format(OAI_LTE_DEPLOY_SCRIPT, oai_hash)

# Home eNB (X310) -> EPC 1.
node_name = "enb1"
enb1 = request.RawPC(node_name)
enb1.component_manager_id = COMP_MANAGER_ID
enb1.hardware_type = params.sdru_nodetype
if params.sdr_compute_image:
    enb1.disk_image = params.sdr_compute_image
else:
    enb1.disk_image = UBUNTU_IMG
enb1_cn_if = enb1.addInterface("{}-cn-if".format(node_name))
enb1_cn_if.addAddress(pg.IPv4Address("192.168.1.2", "255.255.255.0"))
cn_link.addInterface(enb1_cn_if)
node_sdr_if = enb1.addInterface("usrp_if")
node_sdr_if.addAddress(pg.IPv4Address("192.168.30.1", "255.255.255.0"))
sdr_link = request.Link("{}-sdr-link".format(node_name))
sdr_link.addInterface(node_sdr_if)
enb1.addService(pg.Execute(shell="bash", command=enb_build_cmd))
enb1.addService(pg.Execute(shell="bash", command="/local/repository/bin/tune-sdr-iface.sh"))
enb1.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru1ue1 0"))
enb1.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru2ue1 95"))
enb1.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru1ue2 95"))
enb1.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru2ue2 95"))

node_name = "sdru"
sdru = request.RawPC("{}-sdr".format(node_name))
sdru.component_id = NODE_IDS[node_name]
sdr_link.addNode(sdru)
sdru.Desire("rf-controlled", 1)
matrix_nodes[node_name] = sdru

# FBS eNB (N300) -> EPC 2.
node_name = "enb2"
enb2 = request.RawPC(node_name)
enb2_cn_if = enb2.addInterface("{}-cn-if".format(node_name))
enb2_cn_if.addAddress(pg.IPv4Address("192.168.1.3", "255.255.255.0"))
cn_link.addInterface(enb2_cn_if)
enb2.component_manager_id = COMP_MANAGER_ID
enb2.hardware_type = params.sdru2_nodetype
if params.sdr_compute_image:
    enb2.disk_image = params.sdr_compute_image
else:
    enb2.disk_image = UBUNTU_IMG
node_sdr_if = enb2.addInterface("{}-sdr-if".format(node_name))
node_sdr_if.addAddress(pg.IPv4Address("192.168.10.1", "255.255.255.0"))
sdr_link = request.Link("{}-sdr-link".format(node_name))
sdr_link.addInterface(node_sdr_if)
enb2.addService(pg.Execute(shell="bash", command=enb_build_cmd))
enb2.addService(pg.Execute(shell="bash", command="/local/repository/bin/tune-sdr-iface.sh"))
enb2.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens gnb2ue1 95"))
enb2.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens gnb2ue2 95"))

node_name = "sdru2"
sdru2 = request.RawPC("{}-sdr".format(node_name))
sdru2.component_id = NODE_IDS[node_name]
sdr_link.addNode(sdru2)
sdru2.Desire("rf-controlled", 1)
matrix_nodes[node_name] = sdru2

# COTS UE nodes (Quectel RM520, run in LTE mode).
node_name = "ue1"
ue1 = request.RawPC(node_name)
ue1.component_manager_id = COMP_MANAGER_ID
ue1.component_id = NODE_IDS[node_name]
ue1.disk_image = COTS_UE_IMG
ue1.Desire("rf-controlled", 1)
ue1.addService(pg.Execute(shell="bash", command="/local/repository/bin/module-airplane.sh"))
ue1.addService(pg.Execute(shell="bash", command="/local/repository/bin/setup-cots-ue.sh internet"))
matrix_nodes[node_name] = ue1

node_name = "ue2"
ue2 = request.RawPC(node_name)
ue2.component_manager_id = COMP_MANAGER_ID
ue2.component_id = NODE_IDS[node_name]
ue2.disk_image = COTS_UE_IMG
ue2.Desire("rf-controlled", 1)
ue2.addService(pg.Execute(shell="bash", command="/local/repository/bin/module-airplane.sh"))
ue2.addService(pg.Execute(shell="bash", command="/local/repository/bin/setup-cots-ue.sh internet"))
matrix_nodes[node_name] = ue2

rf_ifaces = {}
for node_name, node in matrix_nodes.items():
    for rf_iface_name in RF_IFACES[node_name].values():
        rf_ifaces[rf_iface_name] = node.addInterface(rf_iface_name)

for rf_link_name, rf_iface_names in RF_LINK_NAMES.items():
    rf_link = request.RFLink(rf_link_name)
    for iface_name in rf_iface_names:
        rf_link.addInterface(rf_ifaces[iface_name])


tour = ig.Tour()
tour.Description(ig.Tour.MARKDOWN, tourDescription)
tour.Instructions(ig.Tour.MARKDOWN, tourInstructions)
request.addTour(tour)

pc.printRequestRSpec(request)
