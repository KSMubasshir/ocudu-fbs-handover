# Co-located O-RAN RIC and srsRAN eNodeB Deployment

## Overview

The enhanced `srsepc-fbs-handover-with-oran` profile now supports deploying the O-RAN SC RIC directly on the eNodeB node, eliminating network connectivity issues and simplifying the overall setup.

## Benefits of Co-located Deployment

### ✅ **Advantages**

1. **Simplified Setup**: Single experiment deployment instead of two separate experiments
2. **No Network Issues**: Eliminates shared VLAN configuration and connectivity problems  
3. **Faster Deployment**: No waiting for separate O-RAN experiment to be ready
4. **Resource Efficiency**: Uses existing eNodeB hardware instead of separate node
5. **Consistent E2 Connectivity**: Local E2Term service always available at predictable IP
6. **Easier Troubleshooting**: All components on same node for debugging

### ⚠️ **Considerations**

1. **Resource Usage**: eNodeB node runs both srsRAN and O-RAN RIC (requires adequate CPU/memory)
2. **Hardware Requirements**: Recommend d740 nodes for sufficient resources
3. **Setup Time**: Initial O-RAN RIC deployment adds ~10-15 minutes to boot process
4. **Limited Scalability**: Single-node O-RAN deployment vs. distributed RIC

## How It Works

### **Deployment Architecture**

```
┌─────────────────────────────────────────┐
│              eNB1 Node                  │
├─────────────────────────────────────────┤
│ ┌─────────────┐  ┌─────────────────────┐ │
│ │   srsRAN    │  │    O-RAN SC RIC     │ │
│ │             │  │                     │ │
│ │ - srsEPC    │  │ ├─ ricplt namespace │ │
│ │ - srsENB    │◄─┤ │  - e2term         │ │
│ │ - E2 agent  │  │ │  - e2mgr          │ │
│ │             │  │ │  - submgr         │ │ 
│ └─────────────┘  │ │  - rtmgr          │ │
│                  │ └─ ricinfra         │ │
│                  └─────────────────────┘ │
└─────────────────────────────────────────┘
```

### **Technical Implementation**

1. **Container Platform**: Uses `kind` (Kubernetes in Docker) for lightweight K8s cluster
2. **O-RAN Components**: Deploys essential RIC platform services (ricplt namespace)
3. **E2 Interface**: E2Term service available at Kubernetes cluster IP
4. **Management Scripts**: Automated setup and management tools provided

## Usage Instructions

### **1. Enable Local RIC Deployment**

When instantiating the experiment:
- Set `Deploy O-RAN RIC on eNodeB` parameter to `True`
- Choose adequate hardware type (recommend `d740`)
- **Shared VLAN options are automatically disabled and ignored** when local RIC is enabled

### **2. Experiment Deployment**

The profile will automatically:
- Install Docker, Kubernetes (kind), and Helm on eNB1 node
- Clone O-RAN SC deployment repository
- Create local Kubernetes cluster with O-RAN SC RIC
- Generate management scripts for RIC operations

### **3. Get E2Term Service IP**

On the eNB1 node:
```bash
# Get E2Term service IP for eNodeB configuration
/local/repository/bin/get-e2term-ip.sh

# Or use the management script
/local/repository/bin/manage-oran-ric.sh e2term-ip
```

### **4. Start srsRAN with O-RAN Integration**

```bash
# Get E2Term IP
E2TERM_IP=$(/local/repository/bin/get-e2term-ip.sh | grep "E2Term SCTP IP:" | cut -d' ' -f4)

# Start eNodeB with O-RAN E2 agent
sudo srsenb --ric.agent.remote_ipv4_addr=${E2TERM_IP} --log.all_level=warn --ric.agent.log_level=debug --log.filename=stdout
```

## Management Commands

### **RIC Status and Operations**

```bash
# Check RIC component status
/local/repository/bin/manage-oran-ric.sh status

# View E2Term logs (monitor eNodeB connections)
/local/repository/bin/manage-oran-ric.sh logs e2term-alpha

# View E2Manager logs (connected RAN nodes)
/local/repository/bin/manage-oran-ric.sh logs e2mgr

# Restart RIC services if needed
/local/repository/bin/manage-oran-ric.sh restart
```

### **Direct Kubernetes Access**

```bash
# Check all RIC pods
kubectl get pods -n ricplt

# Check RIC services
kubectl get svc -n ricplt

# Monitor E2 connections in real-time
kubectl logs -f -n ricplt -l app=ricplt-e2term-alpha
```

## Troubleshooting

### **RIC Deployment Issues**

1. **Docker not starting**:
   ```bash
   sudo systemctl status docker
   sudo systemctl start docker
   ```

2. **Kind cluster issues**:
   ```bash
   kind get clusters
   kind delete cluster --name oran-local
   # Re-run setup: /local/repository/bin/setup-oran-local.sh
   ```

3. **RIC pods not starting**:
   ```bash
   kubectl get pods -n ricplt -n ricinfra
   kubectl describe pod <pod-name> -n ricplt
   ```

### **E2 Connection Issues**

1. **E2Term service not available**:
   ```bash
   kubectl get svc -n ricplt service-ricplt-e2term-sctp-alpha
   ```

2. **E2 connection refused**:
   ```bash
   # Check E2Term logs
   kubectl logs -n ricplt -l app=ricplt-e2term-alpha --tail=50
   
   # Test E2Term connectivity
   E2TERM_IP=$(kubectl get svc -n ricplt service-ricplt-e2term-sctp-alpha -o jsonpath='{.spec.clusterIP}')
   telnet $E2TERM_IP 36421
   ```

3. **srsRAN E2 agent issues**:
   - Verify E2Term IP is correct
   - Check srsRAN logs for E2 setup messages
   - Ensure RIC services are running before starting eNodeB

## Performance Considerations

### **Resource Requirements**

- **Minimum**: 16 GB RAM, 8 CPU cores
- **Recommended**: 32 GB RAM, 16 CPU cores (d740 nodes)
- **Storage**: ~10 GB for O-RAN container images

### **Network Performance**

- **Local E2 Interface**: No network latency issues
- **Higher Throughput**: Direct container-to-process communication
- **No VLAN Dependencies**: Eliminates external network variables

## Comparison: Local vs Remote RIC

| Aspect | Local RIC | Remote RIC (Shared VLAN) |
|--------|-----------|-------------------------|
| **Setup Complexity** | ✅ Simple (single experiment, VLAN options disabled) | ❌ Complex (two experiments) |
| **Network Dependencies** | ✅ None (VLAN automatically disabled) | ❌ Requires shared VLAN |  
| **Resource Usage** | ❌ Higher on eNodeB node | ✅ Separate dedicated node |
| **Deployment Time** | ✅ Faster (~25 min total) | ❌ Slower (~40+ min total) |
| **Troubleshooting** | ✅ Single node debugging | ❌ Multi-experiment debugging |
| **E2 Connectivity** | ✅ Always reliable | ❌ Network dependent |
| **Scalability** | ❌ Single-node RIC | ✅ Full distributed RIC |

## Use Cases

### **Recommended for Local RIC**
- O-RAN E2 interface testing and development
- Algorithm development and validation
- Educational demonstrations  
- Proof-of-concept implementations
- Single eNodeB scenarios

### **Recommended for Remote RIC**
- Multi-eNodeB deployments
- Distributed RIC scenarios
- Production-like deployments
- xApp ecosystem testing
- Multi-experiment integration

## Files Added/Modified

### **New Files**
- `bin/setup-oran-local.sh` - O-RAN RIC deployment script
- `bin/get-e2term-ip.sh` - E2Term service IP retrieval
- `bin/manage-oran-ric.sh` - RIC management operations

### **Modified Files**
- `profile.py` - Added local RIC deployment parameter and logic
- Profile instructions updated with local RIC usage patterns

This co-located deployment option provides a much simpler path for users who want to experiment with O-RAN E2 interfaces without the complexity of multi-experiment network configuration!