#!/bin/bash

set -x

GW=$1
SUBNETS=$2

SUDO=/usr/bin/sudo

$SUDO /sbin/iptables -t nat -A POSTROUTING -o `cat /var/emulab/boot/controlif` -j MASQUERADE
$SUDO /sbin/sysctl -w net.ipv4.ip_forward=1
if [ -n "$SUBNETS" ]; then
    for SUBNET in $SUBNETS; do
	$SUDO /sbin/ip route add $SUBNET via $GW
    done
else
    $SUDO /sbin/ip route add 10.233/16 via $GW
    $SUDO /sbin/ip route add 10.96/12 via $GW
fi
