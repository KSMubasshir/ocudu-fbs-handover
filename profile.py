#!/usr/bin/env python

import os

import geni.portal as portal
import geni.rspec.pg as pg
import geni.rspec.igext as ig
import geni.rspec.emulab.pnext as pn
import geni.rspec.emulab as emulab


tourDescription = """
### OCUDU 5G Intra- and Inter-gNB Handover using the Programmable Attenuator Matrix

This profile instantiates a 5G network with OCUDU and Open5GS on POWDER in a conducted RF environment with programmable attenuators for emulating handover scenarios.

The following will be deployed:
- Open5GS CN node (Dell R430)
  - optional (`enable_vnc` parameter, on by default): browser-based VNC desktop reachable from the portal, for the live EPRE waterfall and other GUI tools
- OCUDU CU/DU node (Dell R740 + USRP X310 w/ 2x UBX-160 daughter cards)
  - the two daughter cards will be used for separate DU/RU pairs and intra-gNB handover
  - optional (`enable_phy_tap` parameter): OCUDU built with the upstream PHY tap plugin, exposing UL energy per subcarrier (EPRE) as a ZMQ stream
- Second OCUDU CU/DU node (Dell R740 + USRP N300)
  - a separate gNB (gNB ID 412, PCI 3) attached to the same Open5GS core, for inter-gNB handover with the first one
- 2 Intel NUCs w/ Quectel RM520 COTS UEs)

#### Measurements and observation points

- **Programmable attenuator matrix**: `bin/atten -l` lists the RF paths this experiment controls, `bin/update-attens <group> <0..95>` sets every path of a RU/UE pair (actual attenuation is 30 + value dB), `bin/handover <ue> <ru>` steps one pair up while the other steps down, and `bin/handover-gnb <ue> <gnb>` does the same between the first gNB (RU 1) and the second gNB. Run these on `cudu`; attenuator control hangs on the NUCs.
- **gNB per-UE metrics table** (stdout of the `gnb` process on `cudu`): PCI and RNTI (both change on a handover), DL CQI, rank, MCS, bitrate, HARQ ok/nok and BLER, buffer state; UL PUSCH SNR, RSRP, MCS, bitrate, BLER, BSR, timing advance and power headroom, one row per UE per second.
- **gNB JSON metrics over WebSocket** (port 8001 on `cudu`): NGAP, E1AP, PDCP, RRC, scheduler, RLC, MAC, DU-low and RU layer metrics every 500 ms, logged to a JSONL file with `bin/metrics-receiver.py`. The same interface accepts control commands; `bin/rrm-policy-set.py` sets RRM slice policy ratios on the running gNB as an example.
- **gNB log and packet captures**: `/tmp/gnb.log` (RRC at debug level in the shipped config, so handover signalling is visible), plus MAC and NGAP pcaps that can be switched on in the `pcap` section of the gNB config.
- **UL energy per subcarrier (EPRE) PHY tap** (optional, `enable_phy_tap`): OCUDU built with the upstream PHY tap plugin publishes one float32 vector per UL slot (612 subcarriers for the 20 MHz / 30 kHz SCS cells) on a ZMQ PUSH socket, including slots with nothing scheduled. `bin/epre-sink.py` prints per-slot peak/mean, records the raw stream, and replays it as an EPRE-vs-frequency waterfall. With both cells configured the stream interleaves the two cells' UL slots without a cell tag (see the PHY tap section of the instructions).
- **Second gNB** (`cudu2` with the N300): the matrix connects the N300 to both UEs, so its cell can be faded in and out against the first gNB's cell with the attenuators. Its `gnb` process prints the same per-UE metrics table and writes `/tmp/gnb.log`.
- **COTS UE serving cell and RF readings** (on `ue1`/`ue2`): `bin/ue_metrics.py` polls the modem every second and logs PCI, cell id, TAC, ARFCN, band, bandwidth, RSRP, RSRQ, SINR and TX power as JSON, which confirms a handover from the UE side; `bin/ue_app.py` is an interactive terminal UI for the same modem (power up/down, airplane mode, serving cell, IMSI); `bin/quectel_control.py scan` runs a network scan (`AT+QSCAN`) that lists the cells the modem can see.
- **Core network**: AMF and SMF logs via `journalctl` on `cn5g` show registration, PDU session setup and release; `tshark`/`wireshark` on the `cn5g` N2/N3 interface capture NGAP and GTP-U; the Open5GS subscriber database can be inspected with `open5gs-dbctl` in `/var/tmp`.
- **End-to-end traffic**: `ping` between UE and UPF (`10.45.0.1`) to watch for loss through a handover, and `iperf3` (installed on `cn5g` and the UE nodes) for uplink and downlink throughput.
"""

tourInstructions = """

Startup scripts will still be running when your experiment becomes ready. Watch the "Startup" column on the "List View" tab for your experiment and wait until all of the compute nodes show "Finished" before proceeding.

Once the experiment is ready, you can log into the Open5GS CN node (`cn5g`) and monitor the AMF and SMF logs:

```
# on the cn5g node
sudo journalctl -u open5gs-amfd -u open5gs-smfd -f --output cat
```

Next, in a session on the OCUDU CU/DU node (`cudu`), start the OCUDU
gNB:

```
# on the cudu node
sudo numactl --membind 0 --cpubind 0 \
  /var/tmp/ocudu/build/apps/gnb/gnb -c /var/tmp/etc/ocudu/gnb_rf_x310_ho.yml
```

Note: OCUDU is built against the UHD 4.10 packages vendored in this repository (`debs/`), and the X310 must carry an FPGA image from the same UHD release. If the gNB (or `uhd_usrp_probe --args addr=192.168.30.2`) fails with `RFNoC protocol mismatch between SW and HW`, the radio is running an image for a different UHD release. The X310 is reached on SFP0 at 10 GbE (`192.168.30.2`), which is the XG (dual 10 GbE) image; `fpga=XG` in the loader's device args selects it (without that key the loader reads the variant from the device, and `--fpga-path` can name a bitfile explicitly). Flash the image, then power cycle the SDR: the X310 keeps running the old image until it reboots, and the loader cannot reboot it. Use the power cycle action on the `sdru-sdr` node in the portal's list view, wait for the radio to come back (about a minute), and only then start the gNB:

```
# on the cudu node
sudo uhd_images_downloader -t x3xx    # installs to /usr/share/uhd/4.10.0/images
uhd_image_loader --args="type=x300,addr=192.168.30.2,fpga=XG"
# now power cycle sdru-sdr from the portal, then verify:
uhd_usrp_probe --args addr=192.168.30.2
```

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

The UE nodes also carry systemd units for a modem control server (`quectel-control`), a serving-cell metrics logger (`ue-metrics`) and the connection manager (`quectel-cm`). They are installed but not enabled; manage them with `/local/repository/bin/ue-services start|stop|status`. The `ue_app.py` terminal UI, `ue_metrics.py` and the `quectel_control.py` command line all talk to the control server, so start at least that one first (`sudo systemctl start quectel-control`). Note that `module-on.sh` and `module-airplane.sh` drive the modem's AT port directly and will conflict with a running `quectel-control` service; with the service up, use `uv run bin/quectel_control.py up` (or `airplane`) instead. Python helpers on the UE nodes are run the same way as on `cudu`: `cd /local/repository && uv run bin/ue_app.py`.

At this point the UE should attach to the gNB via the first DU/RU pair. (This profile initializes the state of the programmable attenuators such that the paths between DU/RU 1 and the COTS UE have the minimum attenuation, while the paths terminating at DU/RU 2 have the maximum attenuation.) The physical cell ID (PCI) for this DU/RU pair is 1, as indicated in the output of the OCUDU gNB process...

```
# output of ocudu gnb process on cudu node
          |--------------------DL---------------------|-------------------------UL------------------------------
 pci rnti | cqi  ri  mcs  brate   ok  nok  (%)  dl_bs | pusch  rsrp  mcs  brate   ok  nok  (%)    bsr    ta  phr
   1 4604 |  15   1   27   4.8k    5    0   0%      0 |  37.5  -5.0   28    17k    4    0   0%      0   0us   24
   1 4604 |  15   1   28   4.2k    4    0   0%      0 |  37.9  -5.0   28    13k    3    0   0%      0   0us   24
   1 4604 |  15   1   27   4.8k    5    0   0%      0 |  35.8  -4.9   28    17k    4    0   0%      0   0us   24
   1 4604 |  15   1   27   4.8k    5    0   0%      0 |  36.8  -5.1   28    17k    4    0   0%      0   0us   24
   1 4604 |  15   1   27   4.8k    5    0   0%      0 |  36.3  -5.0   28    22k    5    0   0%      0   0us   24
```

In a session on the `ue1` node, start a ping process pointed at the core network UPF, so we can verify that traffic still passes throughout the handover process:

```
# on ue node
ping 10.45.0.1
```

Now that there is some traffic being generated, lets trigger an intra-gNB handover by incrementally adjusting the attenuations such that the paths between DU/RU 1 and the UE become more attenuated, while the paths terminating at CU/DU 2 become less attenuated, eventually resulting in a higher quality channel between the UE and DU/RU 2. You can use the included helper script to do this:

```
# on the cudu node
/local/repository/bin/handover ue1 ru2
```

You should see the PCI for the attached UE change to 2 in the output of the gNB process, indicating a handover to DU/RU...

```
          |--------------------DL---------------------|-------------------------UL------------------------------
 pci rnti | cqi  ri  mcs  brate   ok  nok  (%)  dl_bs | pusch  rsrp  mcs  brate   ok  nok  (%)    bsr    ta  phr
   2 5601 |  15   1   27   4.7k    5    0   0%      0 |  35.9  -3.0   28    17k    4    0   0%      0   n/a   24
   2 5601 |  15   1   27   4.7k    5    0   0%      0 |  36.5  -4.0   28    17k    4    0   0%      0   n/a   24
   2 5601 |  15   1   27   4.7k    5    0   0%      0 |  37.0  -4.0   28    17k    4    0   0%      0   n/a   24
   2 5601 |  15   1   27   4.7k    5    0   0%      0 |  36.6  -4.0   28    17k    4    0   0%      0   n/a   24
   2 5601 |  15   1   27   4.7k    5    0   0%      0 |  37.0  -4.0   28    17k    4    0   0%      0   n/a   24
   2 5601 |  15   1   27   4.7k    5    0   0%      0 |  36.4  -4.0   28    17k    4    0   0%      0   n/a   24
```

...while the ping traffic continues uninterrupted. You can trigger a handover back to DU/RU #1 if you like:

```
# on the cudu node
/local/repository/bin/handover ue1 ru1
```

The OCUDU gNB publishes metrics in JSON format via WebSocket on port 8001. You can use the included `metrics-receiver.py` script to receive and log these metrics. The Python helper scripts in this profile are run with `uv`, which is installed on the `cudu` node and resolves their dependencies from the repository's `pyproject.toml`:

```
# On, e.g., the `cudu` node, run the following command to receive metrics and log them to a file:
cd /local/repository
uv run bin/metrics-receiver.py --output metrics.jsonl
```

There is another script `rrm-policy-set.py` that can be used to set RRM slice policy ratios on the running gNB, serving as an example for general CU/DU control via the websocket interface. See the script's help for usage information:

```
# On the `cudu` node, run the following command to see usage information:
cd /local/repository
uv run bin/rrm-policy-set.py -h
```

"""

interGnbInstructions = """
#### Inter-gNB handover with the second gNB

The `cudu2` node runs a second, separate OCUDU gNB on the N300 (gNB ID 412, PCI 3), attached to the same Open5GS core. Each gNB lists the other's cell as an external neighbour, and with no Xn link configured the handover goes through the AMF (NG handover).

The external neighbour entry needs the SSB ARFCN of the other cell. Both cells use the same carrier as the intra-gNB config above, so it is one value: note `dl_ssb_arfcn=` in the `Cell pci=1, ...` line the gNB on `cudu` prints at startup with `gnb_rf_x310_ho.yml`, stop that gNB, and write the value into the configs on both gNB nodes (the gNB will not start while the `SSBARFCN` placeholder is in place):

```
# on cudu AND cudu2
sudo sed -i "s/SSBARFCN/<dl_ssb_arfcn>/" /var/tmp/etc/ocudu/gnb*_inter_ho.yml
```

Then start one gNB on each node:

```
# on the cudu node
sudo numactl --membind 0 --cpubind 0 \
  /var/tmp/ocudu/build/apps/gnb/gnb -c /var/tmp/etc/ocudu/gnb1_rf_x310_inter_ho.yml

# on the cudu2 node
sudo /var/tmp/ocudu/build/apps/gnb/gnb -c /var/tmp/etc/ocudu/gnb2_rf_n300_inter_ho.yml
```

Attach `ue1` as above (it starts on gNB 1, PCI 1; the paths to gNB 2 start at maximum attenuation), start the ping, and move it across:

```
# on the cudu node
/local/repository/bin/handover-gnb ue1 gnb2
```

The UE's row disappears from the metrics table on `cudu` and appears with PCI 3 on `cudu2`; `/local/repository/bin/handover-gnb ue1 gnb1` moves it back.

Notes: the N300 gains in `gnb2_rf_n300_inter_ho.yml` are starting values and may need adjusting so both cells arrive at the UE at similar levels. The two radios run on their internal clocks, so the cells are not time aligned. `bin/update-attens gnb2ue1|gnb2ue2` assumes the first eight N300 paths belong to `ue1` and the rest to `ue2`; check against `bin/atten -l`.

"""

phyTapInstructions = """
#### UL EPRE PHY tap

This experiment was instantiated with the `enable_phy_tap` parameter, so OCUDU is built at a dev revision with the upstream PHY tap plugin, which exposes the uplink resource grid to an external processor. The included tap publishes the UL energy per subcarrier (EPRE) of every UL slot as a ZMQ PUSH stream. Start the gNB with the alternate config, which enables the tap and also makes the DU request UL slots that have nothing scheduled (`allow_request_on_empty_uplink_slot`), so the stream flows even before a UE attaches:

```
# on the cudu node
sudo numactl --membind 0 --cpubind 0 \
  /var/tmp/ocudu/build/apps/gnb/gnb -c /var/tmp/etc/ocudu/gnb_rf_x310_ho_phytap.yml
```

The relevant config section is:

```
expert_phy:
  allow_request_on_empty_uplink_slot: true
  enable_phy_tap: true
  phy_tap_arguments: tap_ul_epre=tcp://*:5555,enable_quiet_processing=true,log_level=info
```

Use `epre-sink.py` to consume the stream. In text mode it prints per-slot peak/mean EPRE (expect a few hundred messages per second):

```
# on the cudu node
cd /local/repository
uv run bin/epre-sink.py --endpoint tcp://127.0.0.1:5555
```

To see the waterfall live, open the VNC desktop of the `cn5g` node (VNC button on the portal's list view; available when the experiment was instantiated with `enable_vnc`), and in its xterm connect the plotter to the tap over the experiment LAN:

```
# in the cn5g VNC desktop xterm
cd /local/repository
uv run bin/epre-sink.py --endpoint tcp://192.168.1.2:5555 --plot --scs-khz 30
```

Without VNC, record on the `cudu` node and replay with the plot on a machine with a display (or use `ssh -X`):

```
# on the cudu node
uv run bin/epre-sink.py --endpoint tcp://127.0.0.1:5555 --record /tmp/epre.bin

# on a machine with a display and uv installed
uv run bin/epre-sink.py --replay /tmp/epre.bin --plot --scs-khz 30 --speed 4
```

Bring `ue1` online as described above to see PUCCH/PUSCH occupancy appear in the stream. See `uv run bin/epre-sink.py -h` for all options.

**Limitations.** OCUDU creates the PHY tap factory once per DU rather than once per cell (true on every current OCUDU branch, including `main` and `dev`), and the tap interface carries no cell identity. With the two cells in this profile (PCI 1 and 2) the EPRE stream on port 5555 therefore interleaves both cells' UL slots with no per-message cell tag. To attribute EPRE to a single cell, run a single-cell gNB config; separating cells otherwise needs an upstream change that passes a sector index into `phy_tap_factory::create()`.
"""

BIN_PATH = "/local/repository/bin"
ETC_PATH = "/local/repository/etc"
UBUNTU_IMG = "urn:publicid:IDN+emulab.net+image+emulab-ops//UBUNTU22-64-STD"
COTS_UE_IMG = "urn:publicid:IDN+emulab.net+image+PowderTeam:cots-jammy-image"
COMP_MANAGER_ID = "urn:publicid:IDN+emulab.net+authority+cm"
DEFAULT_OCUDU_HASH = "release_26_04"
# OCUDU dev revision the upstream PHY tap plugin (pinned in bin/common.sh) is
# known to build and run against; release_26_04 lacks the 4-argument
# create_phy_tap_factory() interface the plugin implements.
PHY_TAP_OCUDU_HASH = "90191bd69e"
OPEN5GS_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-open5gs.sh")
OCUDU_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-ocudu.sh")
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
    name="enable_second_gnb",
    description="Include the second gNB (cudu2 + N300) for inter-gNB handover. Disable to instantiate with only the X310 gNB, e.g., when n300-2 is unavailable.",
    typ=portal.ParameterType.BOOLEAN,
    defaultValue=True
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
    name="ocudu_commit_hash",
    description="Commit hash for OCUDU",
    typ=portal.ParameterType.STRING,
    defaultValue="",
    advanced=True
)

pc.defineParameter(
    name="enable_phy_tap",
    description="Build OCUDU with the upstream PHY tap plugin (UL EPRE ZMQ tap). Forces the OCUDU revision to a plugin-compatible dev commit unless ocudu_commit_hash is set.",
    typ=portal.ParameterType.BOOLEAN,
    defaultValue=False,
    advanced=True
)

pc.defineParameter(
    name="enable_vnc",
    description="Start a browser-based VNC desktop on the cn5g node (VNC button in the portal list view); useful for the live EPRE waterfall plot.",
    typ=portal.ParameterType.BOOLEAN,
    defaultValue=True,
    advanced=True
)

params = pc.bindParameters()
pc.verifyParameters()

if not params.enable_second_gnb:
    MATRIX_INPUTS.remove("sdru2")
    MATRIX_GRAPH = dict(
        (k, [n for n in v if n != "sdru2"])
        for k, v in MATRIX_GRAPH.items() if k != "sdru2"
    )

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
if params.enable_vnc:
    cn_node.startVNC()
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
if params.ocudu_commit_hash:
    ocudu_hash = params.ocudu_commit_hash
elif params.enable_phy_tap:
    ocudu_hash = PHY_TAP_OCUDU_HASH
else:
    ocudu_hash = DEFAULT_OCUDU_HASH
phy_tap_arg = "phytap" if params.enable_phy_tap else ""
cmd = "{} '{}' '{}'".format(OCUDU_DEPLOY_SCRIPT, ocudu_hash, phy_tap_arg)
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

if params.enable_second_gnb:
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
instructions = tourInstructions
if params.enable_second_gnb:
    instructions += interGnbInstructions
if params.enable_phy_tap:
    instructions += phyTapInstructions
tour.Instructions(ig.Tour.MARKDOWN, instructions)
request.addTour(tour)

pc.printRequestRSpec(request)
