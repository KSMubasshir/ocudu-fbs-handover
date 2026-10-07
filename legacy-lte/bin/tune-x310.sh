#!/bin/bash

set -x

sudo sysctl -w net.core.wmem_max=24862979

sudo uhd_find_devices \
    || ( echo "ERROR: cannot find radio" && exit 1 )

IFACE=`ip -br -4 addr show | grep '192\.168\.40\.1' | cut -f1 -d' '`
[ -z "$IFACE" ] \
    && (echo "ERROR: cannot find radio iface to set MTU" && exit 1) \
    || sudo ip link set $IFACE mtu 8000
