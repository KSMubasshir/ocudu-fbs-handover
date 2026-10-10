#!/usr/bin/env python

import os

import geni.portal as portal
import geni.rspec.pg as pg
import geni.rspec.igext as ig
import geni.rspec.emulab.pnext as pn
import geni.rspec.emulab as emulab


tourDescription = """
### OAI 5G N2 (Inter-gNB) Handover using the Programmable Attenuator Matrix

This profile instantiates a 5G network with two OpenAirInterface (OAI) gNBs and Open5GS on POWDER in a conducted RF environment with programmable attenuators, for N2 handover (inter-gNB handover through the AMF) as described in the [OAI handover tutorial](https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/doc/handover-tutorial.md#n2-handover).

The following will be deployed:
- Open5GS CN node (Dell R430)
- OAI gNB 1 (Dell R740 + USRP X310, daughter card A): gNB ID 411, PCI 1
- OAI gNB 2 (Dell R740 + USRP N300): gNB ID 412, PCI 3
- 2 Intel NUCs w/ Quectel RM520 COTS UEs

Both gNBs serve one 40 MHz (106 PRB, 30 kHz SCS) band 78 cell on the same carrier and list each other's cell as a neighbour (`etc/oai/neighbour-config.conf`). There is no Xn link, so the handover goes through the AMF.

#### Measurements and observation points

- **Programmable attenuator matrix**: `bin/atten -l` lists the RF paths this experiment controls, `bin/update-attens <group> <0..95>` sets every path of a gNB/UE pair (actual attenuation is 30 + value dB; `ru1ue1`/`ru1ue2` are gNB 1, `gnb2ue1`/`gnb2ue2` are gNB 2), and `bin/handover-gnb <ue> <gnb>` steps one pair up while the other steps down. Run these on `cudu` or `cudu2`; attenuator control hangs on the NUCs.
- **gNB output and log**: `bin/start-oai-gnb` writes the `nr-softmodem` output to `/tmp/gnb.log` (RRC at debug level, NGAP at debug level, so handover signalling is visible). `nrRRC_stats.log` and `nrMAC_stats.log` in `/var/tmp/oai/cmake_targets/ran_build/build` list the connected UEs, their IDs and their measurement reports.
- **gNB telnet server** (127.0.0.1:9090 on each gNB node): `bin/n2-handover <target pci>` sends `ci trigger_n2_ho` to force a handover.
- **COTS UE serving cell and RF readings** (on `ue1`/`ue2`): `bin/ue_metrics.py` polls the modem every second and logs PCI, cell id, TAC, ARFCN, band, bandwidth, RSRP, RSRQ, SINR and TX power as JSON, which confirms a handover from the UE side; `bin/ue_app.py` is an interactive terminal UI for the same modem; `bin/quectel_control.py scan` runs a network scan (`AT+QSCAN`).
- **Core network**: AMF and SMF logs via `journalctl` on `cn5g`; `bin/ngap-capture` on `cn5g` captures NGAP (HandoverRequired, HandoverRequest, HandoverCommand, HandoverNotify) to a pcap.
- **End-to-end traffic**: `ping` between UE and UPF (`10.45.0.1`) to watch for loss through a handover, and `iperf3` (installed on `cn5g`, the gNB nodes and the UE nodes).
"""

tourInstructions = """

Startup scripts will still be running when your experiment becomes ready. Watch the "Startup" column on the "List View" tab for your experiment and wait until all of the compute nodes show "Finished" before proceeding (the OAI build takes a while).

Log into the Open5GS CN node (`cn5g`) and monitor the AMF and SMF logs:

```
# on the cn5g node
sudo journalctl -u open5gs-amfd -u open5gs-smfd -f --output cat
```

Start one gNB on each gNB node. The script picks the node's config, starts `nr-softmodem` with the telnet server and keeps it in the foreground:

```
# on the cudu node (gNB 1, X310, PCI 1)
/local/repository/bin/start-oai-gnb

# on the cudu2 node (gNB 2, N300, PCI 3)
/local/repository/bin/start-oai-gnb
```

Both gNBs should show up in the AMF log (NG Setup). The underlying command is the one from the OAI tutorial with the radio options for each USRP:

```
cd /var/tmp/oai/cmake_targets/ran_build/build
sudo ./nr-softmodem -O /var/tmp/etc/oai/gnb1_x310_n2_ho.conf -E --continuous-tx \
  --gNBs.[0].min_rxtxtime 6 --usrp-tx-thread-config 1 \
  --telnetsrv --telnetsrv.shrmod ci --telnetsrv.listenaddr 127.0.0.1
```

Note: OAI is built against the UHD 4.10 packages vendored in this repository (`debs/`), and the radios must carry FPGA images from the same UHD release. If `nr-softmodem` (or `uhd_usrp_probe --args addr=192.168.30.2`) fails with `RFNoC protocol mismatch between SW and HW`, flash the X310 with `sudo uhd_images_downloader -t x3xx` and `uhd_image_loader --args="type=x300,addr=192.168.30.2,fpga=XG"`, then power cycle `sdru-sdr` from the portal.

In a session on the `ue1` node, start the UE connection manager with the target DNN `internet` in `ipv4` mode:

```
# on the ue node
sudo quectel-CM -s internet -4
```

In another session on the `ue1` node, bring the COTS UE out of airplane mode:

```
# on the ue node
/local/repository/bin/module-on.sh
```

The UE attaches to gNB 1 (PCI 1): this profile initializes the attenuators so the paths between gNB 1 and `ue1` have the minimum attenuation and all other paths the maximum. Start a ping to the UPF so traffic is flowing through the handover (OAI does not hand over a UE without an established PDU session):

```
# on the ue node
ping 10.45.0.1
```

Put both cells on air at similar levels and trigger the N2 handover from the gNB serving the UE. The target is given by its PCI; the UE ID can be left out while the gNB has a single UE:

```
# on the cudu node
/local/repository/bin/update-attens ru1ue1 5
/local/repository/bin/update-attens gnb2ue1 0
/local/repository/bin/n2-handover 3
```

The log of gNB 1 shows `Handover Preparation: send Handover Required (target gNB ID=412, PCI=3)`, the AMF log shows the handover, and the UE continues on gNB 2 (`bin/ue_metrics.py` reports PCI 3). To hand it back:

```
# on the cudu2 node
/local/repository/bin/n2-handover 1
```

Both gNBs also configure periodical reports and an A3 event (neighbour 3 dB better than serving) and start the N2 handover on their own when the UE reports the other cell. To try that, fade the UE across with the attenuators instead of running `n2-handover`:

```
# on the cudu node
/local/repository/bin/handover-gnb ue1 gnb2
```

Whether this works depends on the UE measuring the other cell. The X310 and N300 get no PPS on this testbed, so the two cells are not time aligned; with OCUDU on the same hardware the Quectel modem never reported the neighbour and only forced handovers worked (see `note/troubleshooting.md` section 6). OAI's tutorial likewise asks for radios synchronized to a common clock and time reference, and for the same radio model on both gNBs.

Notes: the gains (`att_tx`, `att_rx`, `max_rxgain` in the `RUs` section of `etc/oai/*.conf`) are OAI's stock values for each radio and may need adjusting so both cells arrive at the UE at similar levels. `bin/start-oai-gnb -c external` switches the radio to the external 10 MHz reference. `bin/update-attens gnb2ue1|gnb2ue2` assumes the first eight N300 paths belong to `ue1` and the rest to `ue2`; check against `bin/atten -l`.

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
