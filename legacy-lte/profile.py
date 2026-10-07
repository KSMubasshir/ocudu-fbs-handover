#!/usr/bin/env python
import geni.portal as portal
import geni.rspec.pg as rspec
import geni.rspec.igext as IG
import geni.rspec.emulab.pnext as PN
import geni.rspec.emulab.emuext
import geni.urn as URN
import hashlib
import os
import socket
import struct

# ======== GLOBAL CONSTANTS ========
class GLOBALS(object):
    BIN_PATH = "/local/repository/bin"
    DEPLOY_SRS = BIN_PATH + "/deploy-srs.sh"
    TUNE_CPU = BIN_PATH + "/tune-cpu.sh"
    TUNE_B210 = BIN_PATH + "/tune-b210.sh"
    SETUP_SRSLTE = BIN_PATH + "/setup-srslte.sh"
    SETUP_IP_CONFIG = BIN_PATH + "/setup-ip-config.sh"
    UPDATE_ENB_CONFIG = BIN_PATH + "/update-enb-config-files.sh"
    UPDATE_UE_CONFIG = BIN_PATH + "/update-ue-config-files.sh"
    NUC_HWTYPE = "nuc5300"
    SRSLTE_IMG = "urn:publicid:IDN+emulab.net+image+PowderProfiles:U18LL-SRSLTE"

# ======== EXPERIMENT DESCRIPTION ========
tourDescription = """
### srsRAN S1 Handover w/ O-RAN Integration

This profile creates a complete LTE testbed with S1 handover capabilities and optional O-RAN RIC integration. 
It deploys srsRAN software on three Intel NUC nodes with B210 SDRs in a controlled RF environment.

#### **Architecture**
- **`ue` node**: srsUE (User Equipment) with B210 SDR
- **`enb1` node**: srsEPC + srsENB (Primary eNodeB + Core Network) 
- **`fake_enb` node**: srsENB (Secondary eNodeB for handover testing)
- **O-RAN Integration Options**:
  - **Local RIC**: Deploy O-RAN SC RIC directly on eNB1 node (simplified setup)
  - **Remote RIC**: Connect to separate O-RAN RIC experiment via shared VLAN

#### **Key Capabilities**
- **Complete LTE Stack**: Full EPC + eNB + UE deployment
- **S1 Handover Testing**: Seamless handover between eNodeBs
- **O-RAN RIC Integration**: E2 agent connectivity with configurable parameters

#### **Parameterization Options**
All key parameters are configurable during experiment instantiation:

**Hardware Configuration:**
- Select specific NUC nodes for each component

**Network Configuration:**  
- Shared VLAN options (only for remote O-RAN integration)
- Custom IP addressing and subnet masks
- Network multiplexing options

**O-RAN Integration:**
- **Local RIC Deployment**: Deploy O-RAN SC RIC directly on eNB1 (no VLAN setup needed)
- **Remote RIC Connection**: Connect to separate O-RAN experiment via shared VLAN
- Gateway address (default: `10.254.254.1`)
- Kubernetes subnets (default: `10.96.0.0/12`)
- Fully customizable for your O-RAN experiment setup

**Advanced Options:**
- VNC remote desktop access
- Network multiplexing control
"""

tourInstructions = """
### Instructions

This profile provides a complete srsRAN S1 handover testbed with O-RAN integration capabilities.

#### **O-RAN Integration Options**

Choose one of two O-RAN deployment methods:

**Option 1: Local RIC Deployment (Recommended)**
- Enable `Deploy O-RAN RIC on eNodeB` parameter during instantiation
- O-RAN SC RIC will be automatically deployed on the eNB1 node
- **No shared VLAN configuration needed** - VLAN options are automatically disabled
- E2Term service runs locally accessible via cluster IP

**Option 2: Remote RIC Connection**
- Disable `Deploy O-RAN RIC on eNodeB` parameter
- Configure shared VLAN parameters for remote O-RAN connectivity
- First start an O-RAN experiment using the companion profile: `https://www.powderwireless.net/p/PowderProfiles/O-RAN`
- Ensure it uses the **same shared VLAN name** configured in this experiment
- Note the **E2Term service IP** from the O-RAN experiment:
  ```bash
  kubectl get svc -n ricplt --field-selector metadata.name=service-ricplt-e2term-sctp-alpha -o jsonpath='{.items[0].spec.clusterIP}'
  ```

#### **Deployment Steps**

**1. Setup and Verification**
All nodes automatically run setup scripts during boot:
- `setup-srslte.sh` - Installs and configures srsRAN software (~5 min)
- `tune-cpu.sh` & `tune-b210.sh` - Optimizes system performance (~2 min)
- `update-*-config-files.sh` - Generates node-specific configurations (~1 min)
- `setup-oran-local.sh` - Deploys O-RAN RIC (if enabled, ~20-25 min)

**For Local O-RAN Setup Progress:**
```bash
# Check setup progress on enb1 (available immediately)
/local/repository/bin/check-oran-setup.sh

# Monitor setup logs in real-time (if needed)
tail -f /var/log/setup-oran-local.log
```

**2. Start Core Network on `enb1`**
```bash
# SSH to enb1 node
ssh enb1

# Start the Evolved Packet Core (EPC)
sudo srsepc
```

**3. Start Primary eNodeB on `enb1`** 
In a new SSH session to `enb1`:

**For Local O-RAN RIC (if enabled in parameters):**
```bash
# Wait for O-RAN setup to complete (~20-25 minutes after node boot)
# Check setup progress: /local/repository/bin/check-oran-setup.sh

# Once setup is complete, get E2Term service IP from local RIC
E2TERM_IP=$(/local/repository/bin/get-e2term-ip.sh | grep "E2Term SCTP IP:" | cut -d' ' -f4)

# Start eNodeB with local RIC integration
sudo srsenb --ric.agent.remote_ipv4_addr=${E2TERM_IP} --log.all_level=warn --ric.agent.log_level=debug --log.filename=stdout

# Monitor RIC status: /local/repository/bin/manage-oran-ric.sh status
```

**For Remote O-RAN RIC (via shared VLAN):**
```bash
# Use E2Term IP from remote O-RAN experiment
sudo srsenb --ric.agent.remote_ipv4_addr=${E2TERM_IP} --log.all_level=warn --ric.agent.log_level=debug --log.filename=stdout
```

**For standalone operation (no O-RAN):**
```bash
sudo srsenb
```

**4. Start Fake eNodeB for Handover Testing**
```bash
# SSH to fake_enb node  
ssh fake_enb

# Start the fake eNodeB (acts as handover target)
sudo srsenb --enb.enb_id=0x20 --enb.cell_id=0x02 --enb.tac=0x0002
```

**5. Start UE and Test Connectivity**
```bash
# SSH to ue node
ssh ue  

# Start the User Equipment
sudo srsue

# In another terminal, test connectivity:
ping 172.16.0.1  # Ping the EPC gateway
```

**6. Observe Handover Events**
- Monitor logs on both `enb1` and `fake_enb` for S1 handover events
- Watch O-RAN RIC interactions (local or remote, if configured)
- UE should seamlessly hand over between the two eNodeBs

#### **Local O-RAN RIC Management**

If you enabled local O-RAN RIC deployment, use these management commands on `enb1`:

```bash
# Check RIC status
/local/repository/bin/manage-oran-ric.sh status

# Get E2Term IP for eNodeB configuration
/local/repository/bin/manage-oran-ric.sh e2term-ip

# Monitor E2 termination logs
/local/repository/bin/manage-oran-ric.sh logs e2term-alpha

# Restart RIC services if needed
/local/repository/bin/manage-oran-ric.sh restart

# Direct kubectl access to RIC
kubectl get pods -n ricplt
kubectl logs -f -n ricplt -l app=ricplt-e2mgr
```

#### **Troubleshooting Local O-RAN**

**RIC not starting:**
1. Check Docker status: `systemctl status docker`
2. Verify kind cluster: `kind get clusters`
3. Check pod status: `kubectl get pods -n ricplt -n ricinfra`

**E2 connection failures:**
1. Verify E2Term service: `kubectl get svc -n ricplt service-ricplt-e2term-sctp-alpha`
2. Check E2Term logs: `kubectl logs -n ricplt -l app=ricplt-e2term-alpha`
3. Test connectivity: `telnet <E2TERM_IP> 36421`

#### **Advanced Configuration**

**Custom UE/eNB Configuration:**
- Configuration files are auto-generated in `/local/etc/srsran/`
- Modify parameters and restart services as needed

**O-RAN RIC Integration:**
- Deploy `kpimon` xApp in O-RAN experiment after eNB connection
- Monitor KPI reports and RIC control messages
- Experiment with RIC-driven handover policies

**Troubleshooting:**
- Check `/var/log/` for service logs
- Verify RF connectivity with `sudo /local/repository/bin/atten`
- Use VNC (if enabled) for graphical debugging tools

#### **Expected Results**
- UE successfully attaches to `enb1`
- Data connectivity through EPC core network  
- Successful S1 handover to `fake_enb`
- O-RAN RIC visibility into handover events (if configured)
"""

# ======== PARAMETER DEFINITIONS ========
pc = portal.Context()

# Define parameter groups for better organization
pc.defineParameterGroup("hardware", "Hardware Configuration")
pc.defineParameterGroup("networking", "Network Configuration") 
pc.defineParameterGroup("oran", "O-RAN Integration")
pc.defineParameterGroup("advanced", "Advanced Options")

# O-RAN Integration
pc.defineParameter("deploy_oran_locally", "Deploy O-RAN RIC on eNodeB", portal.ParameterType.BOOLEAN, False,
    longDescription="Deploy O-RAN SC RIC directly on the eNB1 node instead of using separate experiment. Simplifies setup and eliminates network issues.",
    groupId="oran")

# Hardware Configuration - EPC is optional (if disabled, EPC runs on enb1)
pc.defineParameter("deploy_epc_node", "Deploy separate EPC node", portal.ParameterType.BOOLEAN, False,
    longDescription="Deploy a separate EPC node. If disabled, the EPC will run on the enb1 node.",
    groupId="hardware")
pc.defineParameter("epc_node", "Node for EPC", portal.ParameterType.STRING, "nuc1", groupId="hardware")
pc.defineParameter("enb1_node", "Node for eNB1", portal.ParameterType.STRING, "nuc2", groupId="hardware")
pc.defineParameter("enb2_node", "Node for eNB2", portal.ParameterType.STRING, "nuc4", groupId="hardware")
pc.defineParameter("ue_node", "Node for UE", portal.ParameterType.STRING, "nuc3", groupId="hardware")
# Network Configuration
pc.defineParameter("link_enbs", "Create link between eNodeBs", portal.ParameterType.BOOLEAN, False,
    longDescription="Create an optional network link between the two eNodeBs (enb1 and enb2) for X2 interface or other inter-eNodeB communication.",
    groupId="networking")
pc.defineParameter("shared_vlan", "Shared VLAN name (for remote O-RAN only)", portal.ParameterType.STRING, "", 
    longDescription="Name of an existing shared VLAN to connect to remote O-RAN experiment. Only used when 'Deploy O-RAN RIC on eNodeB' is disabled. Leave empty if using local O-RAN or no O-RAN integration.",
    groupId="networking")
pc.defineParameter(
    "shared_vlan_netmask", "Shared VLAN IP Netmask",
    portal.ParameterType.STRING, "255.255.255.0",
    longDescription="Set the subnet mask for the shared VLAN interface. Only used with remote O-RAN integration.", 
    groupId="networking")
pc.defineParameter(
    "shared_vlan_gateway", "Shared VLAN Gateway Address",
    portal.ParameterType.STRING, "192.168.1.1",
    longDescription="The gateway IP address for the shared VLAN subnet. Only used with remote O-RAN integration.", 
    groupId="networking")
pc.defineParameter(
    "multiplex_lans", "Multiplex Networks",
    portal.ParameterType.BOOLEAN, True,
    longDescription="Multiplex any networks over physical interfaces using VLANs.", 
    groupId="advanced")

# O-RAN Integration Parameters
pc.defineParameter(
    "oran_address", "O-RAN Services Gateway Address",
    portal.ParameterType.STRING, "10.254.254.1",
    longDescription="The IP address of the O-RAN services gateway running on an adjacent experiment connected to the same shared VLAN. Change this to match your O-RAN experiment's gateway address.",
    groupId="oran")
pc.defineParameter(
    "oran_virtual_subnets", "O-RAN Kubernetes Subnets to route via Gateway",
    portal.ParameterType.STRING, "10.96.0.0/12",
    longDescription="A space-separated list of subnets in CIDR format to route via the O-RAN Services Gateway Address. Common values: '10.96.0.0/12' for default Kubernetes, '10.244.0.0/16' for some CNI configurations.",
    groupId="oran")

# Advanced Options
pc.defineParameter(
    "install_vnc", "Install VNC on Compute Nodes",
    portal.ParameterType.BOOLEAN, False,
    longDescription="Install VNC on the compute nodes for remote desktop access.", 
    groupId="advanced")

params = pc.bindParameters()
pc.verifyParameters()

# ======== MAIN EXPERIMENT SETUP ========
request = pc.makeRequestRSpec()

if params.install_vnc:
    request.initVNC()

# ======== HELPER FUNCTIONS ========
def next_ipv4_addr(base_addr_str, mask_str, offset):
    """
    Calculate the next IP address given a base address, netmask, and offset.
    """
    bai = struct.unpack(">i", socket.inet_aton(base_addr_str))[0]
    mi = struct.unpack(">i", socket.inet_aton(mask_str))[0]
    ni = bai + offset
    if bai & mi != ni & mi:
        raise Exception("insufficient space in netmask %s to increment %s + %d" % (
            mask_str, base_addr_str, offset))
    return socket.inet_ntoa(struct.pack(">i", ni))

def add_epc_services(epc):
    """
    Adds services for EPC node.
    """
    epc.addService(rspec.Execute(shell="bash", command="/local/repository/bin/tune-cpu.sh"))
    epc.addService(rspec.Execute(shell="bash", command="/local/repository/bin/setup-srslte.sh"))
    if params.install_vnc:
        epc.startVNC()

def add_ue_services(ue, ue_index):
    """
    Adds services for UE nodes following srslte-shvlan-oran pattern.
    """
    ue.addService(rspec.Execute(shell="bash", command="/local/repository/bin/tune-cpu.sh"))
    ue.addService(rspec.Execute(shell="bash", command="/local/repository/bin/tune-b210.sh"))
    ue.addService(rspec.Execute(shell="bash", command="/local/repository/bin/setup-srslte.sh"))
    # Generate UE configuration with unique IMSI
    imsi = "001010{:06d}{:03d}".format(12345, ue_index)
    imei = "353490{:06d}{:03d}".format(12345, ue_index)
    ue.addService(rspec.Execute(shell="bash", command="/local/repository/bin/update-ue-config-files.sh '%s,%s'" % (imsi, imei)))
    if params.install_vnc:
        ue.startVNC()

def add_enb_services(enb, enb_index):
    """
    Adds services for eNodeB nodes following srslte-shvlan-oran pattern.
    """
    enb.addService(rspec.Execute(shell="bash", command="/local/repository/bin/tune-cpu.sh"))
    enb.addService(rspec.Execute(shell="bash", command="/local/repository/bin/tune-b210.sh"))
    
    # Deploy O-RAN RIC locally on eNB1 if enabled (only on the primary eNodeB)
    if params.deploy_oran_locally and enb_index == 1:
        # Install Docker and Kubernetes
        enb.addService(rspec.Execute(shell="bash", command="/local/repository/bin/setup-oran-local.sh"))
    
    # Add O-RAN IP configuration only for remote O-RAN (not needed for local RIC)
    if params.shared_vlan and not params.deploy_oran_locally:
        enb.addService(rspec.Execute(shell="bash", command="/local/repository/bin/setup-ip-config.sh %s '%s'" % (params.oran_address, params.oran_virtual_subnets)))
    
    enb.addService(rspec.Execute(shell="bash", command="/local/repository/bin/setup-srslte.sh"))
    
    # Configure eNB with UE information (simplified for handover scenario)
    imsi = "001010{:06d}001".format(12345)  # Use consistent IMSI for handover
    imei = "353490{:06d}001".format(12345)
    ue_ip = "192.168.0.10"
    enb.addService(rspec.Execute(shell="bash", command="/local/repository/bin/update-enb-config-files.sh '0x{:03x}' '{},{},{},{}'".format(enb_index, 1, imsi, imei, ue_ip)))
    
    if params.install_vnc:
        enb.startVNC()

def add_services(node, role):
    """
    Legacy function for backward compatibility - redirects to specific service functions.
    """
    if role == "EPC":
        add_epc_services(node)
    elif role == "UE":
        add_ue_services(node, 1)
    elif role in ["eNodeB1", "eNodeB2"]:
        add_enb_services(node, 1 if role == "eNodeB1" else 2)

def create_node(name, component_id, role):
    """
    Creates a node with the specified name and hardware type.
    """
    node = request.RawPC(name)
    node.hardware_type = GLOBALS.NUC_HWTYPE
    node.component_id = component_id
    node.disk_image = GLOBALS.SRSLTE_IMG
    node.Desire("rf-controlled", 1)
    add_services(node, role)
    return node

def create_interface(node, iface_name, ip_address=None, vlan_name=None):
    """
    Creates an interface for the node.
    """
    iface = node.addInterface(iface_name)
    if ip_address:
        iface.addAddress(rspec.IPv4Address(ip_address, "255.255.255.0"))
    if vlan_name:
        iface.vlan_name = vlan_name
    return iface

def connect_shared_vlan(node, vlan_name, ip_address, netmask):
    """
    Connects the node to the shared VLAN with full configuration support.
    """
    iface = node.addInterface("ifSharedVlan")
    if ip_address:
        iface.addAddress(rspec.IPv4Address(ip_address, netmask))
    link = request.Link(node.name + "-shvlan")
    link.addInterface(iface)
    link.connectSharedVlan(vlan_name)
    if params.multiplex_lans:
        link.link_multiplexing = True
        link.best_effort = True

# ======== SETUP NODES ========
# Setup optional EPC node
if params.deploy_epc_node:
    epc = request.RawPC("epc")
    epc.hardware_type = GLOBALS.NUC_HWTYPE
    epc.component_id = params.epc_node
    epc.disk_image = GLOBALS.SRSLTE_IMG
    add_epc_services(epc)
    epc_enb1_iface = create_interface(epc, "epc_enb1", "10.20.20.1")
    epc_enb2_iface = create_interface(epc, "epc_enb2", "10.20.21.1")

# Setup UE node
ue = request.RawPC("ue")
ue.hardware_type = GLOBALS.NUC_HWTYPE
ue.component_id = params.ue_node
ue.disk_image = GLOBALS.SRSLTE_IMG
ue.Desire("rf-controlled", 1)
add_ue_services(ue, 1)
ue_enb1_rf = create_interface(ue, "ue_enb1_rf")
ue_enb2_rf = create_interface(ue, "ue_enb2_rf")

# Setup first eNodeB
enb1 = request.RawPC("enb1")
enb1.hardware_type = GLOBALS.NUC_HWTYPE
enb1.component_id = params.enb1_node
enb1.disk_image = GLOBALS.SRSLTE_IMG
enb1.Desire("rf-controlled", 1)
add_enb_services(enb1, 1)
enb1_ue_rf = create_interface(enb1, "enb1_ue_rf")
if params.deploy_epc_node:
    enb1_epc_iface = create_interface(enb1, "enb1_epc", "10.20.20.2")
if params.link_enbs:
    enb1_to_enb2 = create_interface(enb1, "enb1_to_enb2", "10.10.10.1")

# Setup second eNodeB
enb2 = request.RawPC("enb2")
enb2.hardware_type = GLOBALS.NUC_HWTYPE
enb2.component_id = params.enb2_node
enb2.disk_image = GLOBALS.SRSLTE_IMG
enb2.Desire("rf-controlled", 1)
add_enb_services(enb2, 2)
enb2_ue_rf = create_interface(enb2, "enb2_ue_rf")
if params.deploy_epc_node:
    enb2_epc_iface = create_interface(enb2, "enb2_epc", "10.20.21.2")
if params.link_enbs:
    enb2_to_enb1 = create_interface(enb2, "enb2_to_enb1", "10.10.10.2")

# ======== SETUP NETWORK LINKS ========
# Create RF links between eNodeBs and UE
rflink1 = request.RFLink("rflink1")
rflink1.addInterface(enb1_ue_rf)
rflink1.addInterface(ue_enb1_rf)

rflink2 = request.RFLink("rflink2")
rflink2.addInterface(enb2_ue_rf)
rflink2.addInterface(ue_enb2_rf)

# Create links between EPC and eNodeBs (S1 interface)
if params.deploy_epc_node:
    epc_enb1_link = request.Link("epc_enb1_link")
    epc_enb1_link.addInterface(epc_enb1_iface)
    epc_enb1_link.addInterface(enb1_epc_iface)
    if params.multiplex_lans:
        epc_enb1_link.link_multiplexing = True
        epc_enb1_link.best_effort = True
    
    epc_enb2_link = request.Link("epc_enb2_link")
    epc_enb2_link.addInterface(epc_enb2_iface)
    epc_enb2_link.addInterface(enb2_epc_iface)
    if params.multiplex_lans:
        epc_enb2_link.link_multiplexing = True
        epc_enb2_link.best_effort = True

# Create optional link between eNodeBs (for X2 interface or inter-eNB communication)
if params.link_enbs:
    enb_link = request.Link("enb_link")
    enb_link.addInterface(enb1_to_enb2)
    enb_link.addInterface(enb2_to_enb1)
    if params.multiplex_lans:
        enb_link.link_multiplexing = True
        enb_link.best_effort = True

# Create shared VLAN only for remote O-RAN integration (not needed for local RIC)
if params.shared_vlan and not params.deploy_oran_locally:
    # Calculate IP addresses for each node using O-RAN address as base
    enb1_ip = next_ipv4_addr(params.oran_address, params.shared_vlan_netmask, 1)
    enb2_ip = next_ipv4_addr(params.oran_address, params.shared_vlan_netmask, 2)
    
    # Connect nodes to shared VLAN
    connect_shared_vlan(enb1, params.shared_vlan, enb1_ip, params.shared_vlan_netmask)
    connect_shared_vlan(enb2, params.shared_vlan, enb2_ip, params.shared_vlan_netmask)

# ======== TOUR INFORMATION ========
tour = IG.Tour()
tour.Description(IG.Tour.MARKDOWN, tourDescription)
tour.Instructions(IG.Tour.MARKDOWN, tourInstructions)
request.addTour(tour)

# Print the RSpec request
pc.printRequestRSpec(request)
