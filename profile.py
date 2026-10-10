#!/usr/bin/env python

import os

import geni.portal as portal
import geni.rspec.pg as pg
import geni.rspec.igext as ig
import geni.rspec.emulab.pnext as pn
import geni.rspec.emulab as emulab


tourDescription = """
### OAI 5G: a second gNB on its own core with a foreign PLMN

This profile instantiates two independent OpenAirInterface (OAI) 5G networks on POWDER in a conducted RF environment with programmable attenuators. gNB 2 is **not** attached to the same core as gNB 1; it has its own Open5GS core broadcasting a different PLMN, so it is a separate network with no Xn/N2 link and no shared core. A 5G gNB cannot run without a core (it needs an AMF for NG Setup and to establish PDU sessions), so a second core is deployed for it.

The following will be deployed:
- Open5GS core 1 (`cn5g`, Dell R430), PLMN 999/99 (home)
- OAI gNB 1 (`cudu`, Dell R740 + USRP X310, daughter card A) -> core 1: gNB ID 411, PCI 1
- Open5GS core 2 (`cn5g2`, Dell R430), PLMN 001/01 (foreign)
- OAI gNB 2 (`cudu2`, Dell R740 + USRP N300) -> core 2: gNB ID 412, PCI 3
- 2 Intel NUCs w/ Quectel RM520 COTS UEs

Each gNB serves one 40 MHz (106 PRB, 30 kHz SCS) band 78 cell, on separate carriers: gNB 1 at 3619.2 MHz (SSB ARFCN 641280), gNB 2 at 3319.68 MHz (SSB ARFCN 621312), so a modem network scan lists gNB 2's cell as its own entry. The Quectel SIMs are homed on 999/99, so in SA the UE registers on gNB 1 (core 1) and does not register on gNB 2's foreign PLMN; gNB 2 is there to be seen/measured and to be driven from its own core.

#### Measurements and observation points

- **Programmable attenuator matrix**: `bin/atten -l` lists the RF paths this experiment controls, `bin/update-attens <group> <0..95>` sets every path of a gNB/UE pair (actual attenuation is 30 + value dB; `ru1ue1`/`ru1ue2` are gNB 1, `gnb2ue1`/`gnb2ue2` are gNB 2), and `bin/handover-gnb <ue> <gnb>` steps one pair up while the other steps down. Run these on `cudu` or `cudu2`; attenuator control hangs on the NUCs.
- **gNB output and log**: `bin/start-oai-gnb` writes the `nr-softmodem` output to `/tmp/gnb.log` (RRC and NGAP at debug level). `nrRRC_stats.log` and `nrMAC_stats.log` in `/var/tmp/oai/cmake_targets/ran_build/build` list the connected UEs, their IDs and their measurement reports.
- **COTS UE serving cell and RF readings** (on `ue1`/`ue2`): `bin/ue_metrics.py` polls the modem every second and logs PCI, cell id, TAC, ARFCN, band, bandwidth, RSRP, RSRQ, SINR and TX power as JSON; `bin/ue_app.py` is an interactive terminal UI for the same modem; `bin/quectel_control.py scan` runs a network scan (`AT+QSCAN`) that lists the cells and their PLMNs the modem can see, including the foreign one.
- **Both cores**: AMF and SMF logs via `journalctl` on `cn5g` and `cn5g2`; `bin/ngap-capture` on either captures that core's NGAP to a pcap.
- **End-to-end traffic**: `ping` between the UE and its core's UPF (`10.45.0.1`), and `iperf3` (installed on the cores, the gNB nodes and the UE nodes).
"""

tourInstructions = """

Startup scripts will still be running when your experiment becomes ready. Watch the "Startup" column on the "List View" tab for your experiment and wait until all of the compute nodes show "Finished" before proceeding (the OAI build takes a while).

Log into each core and monitor its AMF and SMF logs:

```
# on the cn5g node (core 1, PLMN 999/99)
sudo journalctl -u open5gs-amfd -u open5gs-smfd -f --output cat

# on the cn5g2 node (core 2, PLMN 001/01)
sudo journalctl -u open5gs-amfd -u open5gs-smfd -f --output cat
```

Start one gNB on each gNB node. The script picks the node's config (gNB 1 -> core 1 on `cudu`, gNB 2 -> core 2 on `cudu2`), starts `nr-softmodem` and keeps it in the foreground, writing to `/tmp/gnb.log`:

```
# on the cudu node (gNB 1, X310, PCI 1, PLMN 999/99)
/local/repository/bin/start-oai-gnb

# on the cudu2 node (gNB 2, N300, PCI 3, PLMN 001/01)
/local/repository/bin/start-oai-gnb
```

gNB 1 should complete NG Setup in the `cn5g` AMF log and gNB 2 in the `cn5g2` AMF log.

Note: OAI is built against the UHD 4.10 packages vendored in this repository (`debs/`), and the radios must carry FPGA images from the same UHD release. If `nr-softmodem` (or `uhd_usrp_probe --args addr=192.168.30.2`) fails with `RFNoC protocol mismatch between SW and HW`, flash the X310 with `sudo uhd_images_downloader -t x3xx` and `uhd_image_loader --args="type=x300,addr=192.168.30.2,fpga=XG"`, then power cycle `sdru-sdr` from the portal.

In a session on the `ue1` node, start the UE connection manager with the target DNN `internet` in `ipv4` mode, and in another session bring the COTS UE out of airplane mode:

```
# on the ue node
sudo quectel-CM -s internet -4
```

```
# on the ue node
/local/repository/bin/module-on.sh
```

The UE registers on gNB 1 / core 1 (home PLMN 999/99): this profile initializes the attenuators so the paths between gNB 1 and `ue1` have the minimum attenuation and all other paths the maximum. Confirm the serving cell and PLMN, and ping the UPF:

```
# on the ue node
cd /local/repository && uv run bin/ue_metrics.py

# on the ue node
ping 10.45.0.1
```

Bring gNB 2's cell up at `ue1` with the attenuators and run a network scan: the modem should see the foreign-PLMN cell but stay registered on gNB 1, since 001/01 is not its home network in SA.

```
# on the cudu node
/local/repository/bin/update-attens gnb2ue1 0

# on the ue node
cd /local/repository && uv run bin/quectel_control.py scan
```

Notes: the gains (`att_tx`, `att_rx`, `max_rxgain` in the `RUs` section of `etc/oai/*.conf`) are OAI's stock values for each radio and may need adjusting. `bin/start-oai-gnb -c external` switches a radio to the external 10 MHz reference. The foreign PLMN is set in `etc/oai/gnb2_n300_core2.conf` (gNB broadcast) and passed to `bin/deploy-open5gs.sh` for `cn5g2` (core); change both together. `bin/update-attens gnb2ue1|gnb2ue2` assumes the first eight N300 paths belong to `ue1` and the rest to `ue2`; check against `bin/atten -l`.

"""

BIN_PATH = "/local/repository/bin"
ETC_PATH = "/local/repository/etc"
UBUNTU_IMG = "urn:publicid:IDN+emulab.net+image+emulab-ops//UBUNTU22-64-STD"
COTS_UE_IMG = "urn:publicid:IDN+emulab.net+image+PowderTeam:cots-jammy-image"
COMP_MANAGER_ID = "urn:publicid:IDN+emulab.net+authority+cm"
# OAI develop as of 2026-10-04; the configs in etc/oai are derived from the
# reference configs of this revision.
DEFAULT_OAI_HASH = "f8f769592a7030be88ede4bb5ca66fa1ca6a80e0"
OPEN5GS_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-open5gs.sh")
OAI_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-oai.sh")
# Foreign PLMN broadcast by gNB 2 and its own core (cn5g2). It must match
# plmn_list in etc/oai/gnb2_n300_core2.conf. Given as separate MCC/MNC digit
# strings so the leading zeros survive into the Open5GS config.
FOREIGN_MCC = "001"
FOREIGN_MNC = "01"
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
    description="Type of compute node paired with the RU SDR",
    typ=portal.ParameterType.STRING,
    defaultValue=node_types[1],
    legalValues=node_types
)

pc.defineParameter(
    name="sdru2_nodetype",
    description="Type of compute node paired with the second gNB's SDR",
    typ=portal.ParameterType.STRING,
    defaultValue=node_types[1],
    legalValues=node_types
)

pc.defineParameter(
    name="cn_nodetype",
    description="Type of compute node to use for CN node",
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
    description="Commit hash, branch or tag for OAI (openairinterface5g)",
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

role = "cn5g"
cn_node = request.RawPC(role)
cn_node.component_manager_id = COMP_MANAGER_ID
cn_node.hardware_type = params.cn_nodetype
cn_node.disk_image = UBUNTU_IMG
cn_if = cn_node.addInterface("{}-if".format(role))
cn_if.addAddress(pg.IPv4Address("192.168.1.1", "255.255.255.0"))
cn_link = request.Link("{}-link".format(role))
cn_link.setNoBandwidthShaping()
cn_link.addInterface(cn_if)
cn_node.addService(pg.Execute(shell="bash", command=OPEN5GS_DEPLOY_SCRIPT))

# Second, independent core for gNB 2: its own Open5GS broadcasting the foreign
# PLMN. The deploy script binds NGAP and N3 to this node's 192.168.1.4 and
# provisions subscribers under FOREIGN_MCC/FOREIGN_MNC.
role = "cn5g2"
cn2_node = request.RawPC(role)
cn2_node.component_manager_id = COMP_MANAGER_ID
cn2_node.hardware_type = params.cn_nodetype
cn2_node.disk_image = UBUNTU_IMG
cn2_if = cn2_node.addInterface("{}-if".format(role))
cn2_if.addAddress(pg.IPv4Address("192.168.1.4", "255.255.255.0"))
cn_link.addInterface(cn2_if)
cn2_cmd = "{} {} {}".format(OPEN5GS_DEPLOY_SCRIPT, FOREIGN_MCC, FOREIGN_MNC)
cn2_node.addService(pg.Execute(shell="bash", command=cn2_cmd))

# collect node objects for RF matrix
matrix_nodes = {}

node_name = "cudu"
cudu = request.RawPC(node_name)
cudu.component_manager_id = COMP_MANAGER_ID
cudu.hardware_type = params.sdru_nodetype
if params.sdr_compute_image:
    cudu.disk_image = params.sdr_compute_image
else:
    cudu.disk_image = UBUNTU_IMG
cudu_cn_if = cudu.addInterface("{}-cn-if".format(node_name))
cudu_cn_if.addAddress(pg.IPv4Address("192.168.1.2", "255.255.255.0"))
cn_link.addInterface(cudu_cn_if)
node_sdr_if = cudu.addInterface("usrp_if")
node_sdr_if.addAddress(pg.IPv4Address("192.168.30.1", "255.255.255.0"))
sdr_link = request.Link("{}-sdr-link".format(node_name))
# sdr_link.bandwidth = 10*1000*1000
sdr_link.addInterface(node_sdr_if)
if params.oai_commit_hash:
    oai_hash = params.oai_commit_hash
else:
    oai_hash = DEFAULT_OAI_HASH
cmd = "{} '{}'".format(OAI_DEPLOY_SCRIPT, oai_hash)
cudu.addService(pg.Execute(shell="bash", command=cmd))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/tune-sdr-iface.sh"))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru1ue1 0"))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru2ue1 95"))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru1ue2 95"))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru2ue2 95"))

node_name = "sdru"
sdru = request.RawPC("{}-sdr".format(node_name))
sdru.component_id = NODE_IDS[node_name]
sdr_link.addNode(sdru)
sdru.Desire("rf-controlled", 1)
matrix_nodes[node_name] = sdru

node_name = "cudu2"
cudu2 = request.RawPC(node_name)
cudu2_cn_if = cudu2.addInterface("{}-cn-if".format(node_name))
cudu2_cn_if.addAddress(pg.IPv4Address("192.168.1.3", "255.255.255.0"))
cn_link.addInterface(cudu2_cn_if)
cudu2.component_manager_id = COMP_MANAGER_ID
cudu2.hardware_type = params.sdru2_nodetype
if params.sdr_compute_image:
    cudu2.disk_image = params.sdr_compute_image
else:
    cudu2.disk_image = UBUNTU_IMG
node_sdr_if = cudu2.addInterface("{}-sdr-if".format(node_name))
node_sdr_if.addAddress(pg.IPv4Address("192.168.10.1", "255.255.255.0"))
sdr_link = request.Link("{}-sdr-link".format(node_name))
# sdr_link.bandwidth = 10*1000*1000
sdr_link.addInterface(node_sdr_if)
cudu2.addService(pg.Execute(shell="bash", command=cmd))
cudu2.addService(pg.Execute(shell="bash", command="/local/repository/bin/tune-sdr-iface.sh"))
cudu2.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens gnb2ue1 95"))
cudu2.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens gnb2ue2 95"))

node_name = "sdru2"
sdru2 = request.RawPC("{}-sdr".format(node_name))
sdru2.component_id = NODE_IDS[node_name]
sdr_link.addNode(sdru2)
sdru2.Desire("rf-controlled", 1)
matrix_nodes[node_name] = sdru2

# ue nodes with COTS UE and B210
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
