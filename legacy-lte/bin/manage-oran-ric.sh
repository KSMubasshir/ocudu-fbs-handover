#!/bin/bash

# O-RAN RIC Management Script
# Provides various management operations for the locally deployed O-RAN RIC

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_usage() {
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  status     - Show O-RAN RIC deployment status"
    echo "  e2term-ip  - Get E2Term service IP address"
    echo "  pods       - List all RIC pods"
    echo "  services   - List all RIC services"
    echo "  logs       - Show logs from RIC components"
    echo "  restart    - Restart RIC deployment"
    echo "  cleanup    - Remove RIC deployment"
    echo "  help       - Show this help message"
}

check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        echo "Error: kubectl is not installed or not in PATH"
        exit 1
    fi
}

check_ric_namespace() {
    if ! kubectl get namespace ricplt &> /dev/null; then
        echo "Error: O-RAN RIC namespace 'ricplt' not found. Is the RIC deployed?"
        exit 1
    fi
}

show_status() {
    echo "=========================================="
    echo "O-RAN RIC Deployment Status"
    echo "=========================================="
    echo ""
    
    # Check namespace
    if kubectl get namespace ricplt &> /dev/null; then
        echo "✓ RIC namespace 'ricplt' exists"
    else
        echo "✗ RIC namespace 'ricplt' not found"
        return 1
    fi
    
    # Check pods
    echo ""
    echo "Pod Status:"
    kubectl get pods -n ricplt --no-headers | while read line; do
        name=$(echo $line | awk '{print $1}')
        status=$(echo $line | awk '{print $3}')
        if [[ "$status" == "Running" ]]; then
            echo "  ✓ $name: $status"
        else
            echo "  ✗ $name: $status"
        fi
    done
    
    # Check services
    echo ""
    echo "Service Status:"
    kubectl get services -n ricplt --no-headers | while read line; do
        name=$(echo $line | awk '{print $1}')
        cluster_ip=$(echo $line | awk '{print $3}')
        echo "  ✓ $name: $cluster_ip"
    done
    
    # Get E2Term IP
    echo ""
    E2TERM_IP=$(kubectl get service e2term-sctp-alpha -n ricplt -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "N/A")
    echo "E2Term Service IP: $E2TERM_IP"
}

get_e2term_ip() {
    "$SCRIPT_DIR/get-e2term-ip.sh"
}

show_pods() {
    check_kubectl
    check_ric_namespace
    echo "O-RAN RIC Pods:"
    kubectl get pods -n ricplt
}

show_services() {
    check_kubectl
    check_ric_namespace
    echo "O-RAN RIC Services:"
    kubectl get services -n ricplt
}

show_logs() {
    check_kubectl
    check_ric_namespace
    echo "Recent logs from E2Term:"
    kubectl logs -n ricplt --tail=50 -l app=ricplt-e2term || echo "No E2Term logs found"
    echo ""
    echo "Recent logs from E2Manager:"
    kubectl logs -n ricplt --tail=50 -l app=ricplt-e2mgr || echo "No E2Manager logs found"
}

restart_ric() {
    check_kubectl
    check_ric_namespace
    echo "Restarting O-RAN RIC deployment..."
    kubectl delete pods -n ricplt --all
    echo "Pods deleted. Kubernetes will recreate them automatically."
    echo "Wait a few moments for pods to restart..."
    sleep 5
    kubectl get pods -n ricplt
}

cleanup_ric() {
    check_kubectl
    echo "Warning: This will completely remove the O-RAN RIC deployment!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing O-RAN RIC deployment..."
        kubectl delete namespace ricplt --ignore-not-found=true
        if command -v kind &> /dev/null; then
            kind delete cluster --name oran-local
        fi
        echo "O-RAN RIC cleanup completed."
    else
        echo "Cleanup cancelled."
    fi
}

# Main script logic
if [ $# -eq 0 ]; then
    print_usage
    exit 1
fi

case "$1" in
    status)
        check_kubectl
        show_status
        ;;
    e2term-ip)
        check_kubectl
        check_ric_namespace
        get_e2term_ip
        ;;
    pods)
        show_pods
        ;;
    services)
        show_services
        ;;
    logs)
        show_logs
        ;;
    restart)
        restart_ric
        ;;
    cleanup)
        cleanup_ric
        ;;
    help|--help|-h)
        print_usage
        ;;
    *)
        echo "Error: Unknown command '$1'"
        echo ""
        print_usage
        exit 1
        ;;
esac