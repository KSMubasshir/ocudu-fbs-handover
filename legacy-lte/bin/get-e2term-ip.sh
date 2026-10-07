#!/bin/bash

# Get E2Term IP address from the O-RAN RIC deployment
# This script retrieves the cluster IP of the E2Term service

set -e

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed or not in PATH"
    exit 1
fi

# Check if the RIC namespace exists
if ! kubectl get namespace ricplt &> /dev/null; then
    echo "Error: O-RAN RIC namespace 'ricplt' not found. Is the RIC deployed?"
    exit 1
fi

# Get the E2Term service IP
E2TERM_IP=$(kubectl get service service-ricplt-e2term-sctp-alpha -n ricplt -o jsonpath='{.spec.clusterIP}' 2>/dev/null)

if [ -z "$E2TERM_IP" ]; then
    echo "Error: E2Term service not found or not ready"
    echo "Available services in ricplt namespace:"
    kubectl get services -n ricplt
    exit 1
fi

# Check which ports are available
PORTS=$(kubectl get service service-ricplt-e2term-sctp-alpha -n ricplt -o jsonpath='{.spec.ports[*].port}' 2>/dev/null)

echo "E2Term SCTP IP: $E2TERM_IP"
echo "Available ports: $PORTS"
echo ""
echo "For srsRAN connection use:"
if echo "$PORTS" | grep -q "36422"; then
    echo "  --ric.agent.remote_ipv4_addr=$E2TERM_IP (uses default port 36422)"
else
    echo "  --ric.agent.remote_ipv4_addr=$E2TERM_IP --ric.agent.remote_port=36421"
fi