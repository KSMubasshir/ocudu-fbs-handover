#!/bin/bash
# Simple setup progress checker for O-RAN local deployment

LOG_FILE="/var/log/setup-oran-local.log"

echo "=== O-RAN Setup Progress Checker ==="
echo ""

# Check if setup has started
if [ ! -f "$LOG_FILE" ]; then
    echo "❌ O-RAN setup has not started yet"
    echo "The setup-oran-local.sh script may not have been executed"
    exit 1
fi

echo "📋 Setup log file: $LOG_FILE"
echo ""

# Check current status
echo "🔍 Current status:"
if grep -q "O-RAN SC RIC setup completed successfully!" "$LOG_FILE" 2>/dev/null; then
    echo "✅ Setup completed successfully!"
    
    # Show E2Term IP if available
    if E2TERM_IP=$(grep "E2Term SCTP service IP:" "$LOG_FILE" | tail -1 | cut -d' ' -f5); then
        echo "🌐 E2Term service IP: $E2TERM_IP"
    fi
    
    echo ""
    echo "Next steps:"
    echo "  1. Get E2Term IP: /local/repository/bin/get-e2term-ip.sh"
    echo "  2. Check RIC status: /local/repository/bin/manage-oran-ric.sh status"
    echo "  3. Start srsRAN with: sudo srsenb --ric.agent.remote_ipv4_addr=\$E2TERM_IP"
    
elif grep -q "Error:" "$LOG_FILE" 2>/dev/null; then
    echo "❌ Setup encountered errors"
    echo ""
    echo "Recent errors:"
    grep "Error:" "$LOG_FILE" | tail -3
    echo ""
    echo "Check full log: tail -f $LOG_FILE"
    
else
    echo "⏳ Setup in progress..."
    
    # Show current step
    if tail -5 "$LOG_FILE" | grep -q "Installing\|Downloading\|Creating\|Deploying\|Waiting"; then
        echo "Current step: $(tail -5 "$LOG_FILE" | grep -E "Installing|Downloading|Creating|Deploying|Waiting" | tail -1)"
    fi
    
    echo ""
    echo "Monitor progress: tail -f $LOG_FILE"
fi

echo ""
echo "🛠️  Docker status: $(systemctl is-active docker 2>/dev/null || echo "not running")"

if command -v kind &>/dev/null; then
    if kind get clusters 2>/dev/null | grep -q oran-local; then
        echo "☸️  Kind cluster: oran-local (running)"
    else
        echo "☸️  Kind cluster: not created yet"
    fi
else
    echo "☸️  Kind: not installed yet"
fi

if command -v kubectl &>/dev/null && kubectl config current-context &>/dev/null; then
    echo "🎛️  Kubectl: configured"
    if kubectl get pods -n ricplt &>/dev/null; then
        POD_COUNT=$(kubectl get pods -n ricplt --no-headers 2>/dev/null | wc -l)
        READY_COUNT=$(kubectl get pods -n ricplt --no-headers 2>/dev/null | grep Running | wc -l)
        echo "🏃  RIC pods: $READY_COUNT/$POD_COUNT running"
    else
        echo "🏃  RIC pods: not deployed yet"
    fi
else
    echo "🎛️  Kubectl: not configured yet"
fi