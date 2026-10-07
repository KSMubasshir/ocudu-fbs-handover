#!/bin/bash
set -ex
BINDIR=`dirname $0`
source $BINDIR/common.sh

if [ $# -eq 0 ] || [ $# -gt 1 ]; then
    echo "usage: $0 [dnn]"
    exit 1
fi
DNN=$1

install_ue_deps () {
    sudo apt update && sudo apt install -y --no-install-recommends \
      iperf3
    # uv + Python deps for ue_app.py / ue_metrics.py / quectel_control.py
    # (run in place from /local/repository/bin via the repo's .venv).
    $BINDIR/install-uv.sh
}

# Unit files are installed but NOT enabled or started: use
# /local/repository/bin/ue-services start|stop|status, or start
# quectel-control alone, which ue_app.py / ue_metrics.py / the
# quectel_control.py CLI all require.
maybe_add_ue_metrics () {
    if ! test -f /etc/systemd/system/ue-metrics.service; then
        sudo cp $SERVICESDIR/ue-metrics.service /etc/systemd/system/ue-metrics.service
        sudo systemctl daemon-reload
    fi
}

maybe_add_quectel_control () {
    if ! test -f /etc/systemd/system/quectel-control.service; then
        sudo cp $SERVICESDIR/quectel-control.service /etc/systemd/system/quectel-control.service
        sudo systemctl daemon-reload
    fi
}

update_udhcpc_script () {
    sudo cp $BINDIR/default.script /etc/udhcpc/default.script
    sudo chmod +x /etc/udhcpc/default.script
}

maybe_add_quectel_cm () {
    if ! test -f /etc/systemd/system/quectel-cm.service; then
        echo "Configuring UE for DNN $DNN"
        sudo cp $SERVICESDIR/quectel-cm.service /etc/systemd/system/quectel-cm.service
        sudo sed -i "s/internet/$DNN/" /etc/systemd/system/quectel-cm.service
        update_udhcpc_script
        sudo systemctl daemon-reload
    fi
}

install_ue_deps
maybe_add_ue_metrics
maybe_add_quectel_control
maybe_add_quectel_cm
