# srsRAN S1 Handover with O-RAN Integration

## Overview

This POWDER profile implements a complete LTE testbed with S1 handover capabilities and optional O-RAN RIC integration. It provides automated deployment of srsRAN software stack on Intel NUC nodes with B210 SDRs in a controlled RF environment.

## Architecture

```
┌─────────────┐    RF Link 1    ┌─────────────┐
│     UE      │ ←──────────────→ │    eNB1     │
│  (srsUE)    │                  │(srsEPC+srsENB)│
│             │    RF Link 2    │             │
│             │ ←──────────────→ │             │
└─────────────┘                  └─────────────┘
                                        │
                                 Shared VLAN
                                        │
┌─────────────┐                  ┌─────────────┐
│   Fake eNB  │                  │   O-RAN     │
│  (srsENB)   │                  │   RIC       │
│             │                  │ (Optional)  │
└─────────────┘                  └─────────────┘
```

## Key Features

- **Complete LTE Stack**: EPC, eNodeB, and UE components
- **S1 Handover**: Seamless mobility between eNodeBs
- **O-RAN Integration**: E2 agent connectivity with RIC
- **Automated Setup**: Comprehensive configuration scripts
- **Configurable Parameters**: Flexible network and O-RAN settings

## Quick Start

1. **Instantiate the profile** on POWDER platform
2. **Configure parameters** during instantiation:
   - Set shared VLAN for O-RAN connectivity (optional)
   - Customize O-RAN gateway and subnet parameters
   - Select hardware nodes
3. **Follow deployment instructions** in the experiment

## Files Structure

```
├── profile.py              # Main POWDER profile definition
├── bin/                    # Setup and configuration scripts
│   ├── setup-ip-config.sh  # O-RAN routing configuration
│   ├── setup-srslte.sh     # srsRAN software setup
│   ├── tune-*.sh          # Hardware optimization scripts
│   ├── update-*-config-files.sh # Node configuration
│   └── ...
├── etc/srsran/            # Configuration templates
└── README.md              # This file
```

## Parameters

### Hardware Configuration
- `enb1_node`: Primary eNodeB node selection
- `enbfake_node`: Secondary eNodeB node selection  
- `ue_node`: UE node selection

### Network Configuration
- `shared_vlan`: VLAN name for O-RAN connectivity
- `shared_vlan_netmask`: Subnet mask (default: 255.255.255.0)
- `shared_vlan_gateway`: Gateway IP address

### O-RAN Integration
- `oran_address`: O-RAN services gateway (default: 10.254.254.1)
- `oran_virtual_subnets`: Kubernetes subnets (default: 10.96.0.0/12)

### Advanced Options
- `multiplex_lans`: Enable network multiplexing
- `install_vnc`: Remote desktop access

## Usage Scenarios

### Scenario 1: Standalone LTE Handover
- Leave `shared_vlan` empty
- Focus on S1 handover between eNodeBs
- Study mobility algorithms and performance

### Scenario 2: O-RAN Integration
- Set `shared_vlan` to connect with O-RAN experiment
- Configure O-RAN parameters to match RIC setup
- Deploy RIC applications and monitor handover events

## Troubleshooting

- **Check logs**: `/var/log/` contains service logs
- **RF verification**: Use `/local/repository/bin/atten` for RF testing  
- **VNC access**: Enable VNC parameter for graphical debugging
- **Script status**: Check `/local/etc/` for setup completion markers

## Related Profiles

- **O-RAN RIC**: `https://www.powderwireless.net/p/PowderProfiles/O-RAN`
- **srsLTE Base**: `https://www.powderwireless.net/p/PowderTeam/srslte-shvlan-oran`

## Support

For issues and questions:
- POWDER Platform documentation
- srsRAN community resources
- O-RAN Alliance specifications