#!/bin/bash
set -ex
# deploy-open5gs.sh [<mcc> <mnc>]
# Install Open5GS and provision the two subscribers. Without arguments this is
# core 1 (cn5g, PLMN 999/99). With <mcc> <mnc> it is a second, independent core
# on another node (cn5g2) broadcasting a different PLMN; give the digits exactly
# as they appear in the PLMN, e.g. "001 01". NGAP and N3 GTP-U are bound to this
# node's own 192.168.1.x address either way.
BINDIR=`dirname $0`
source $BINDIR/common.sh

MCC=${1:-999}
MNC=${2:-99}
LANIP=$(ip -4 -o addr show | awk '{print $4}' | grep '^192\.168\.1\.' | cut -d/ -f1)

sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -t nat -A POSTROUTING -s 10.45.0.0/16 ! -o ogstun -j MASQUERADE

if [ -f $SRCDIR/open5gs-setup-complete ]; then
    echo "setup already ran; not running again"
    exit 0
fi

sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:open5gs/latest
sudo add-apt-repository -y ppa:wireshark-dev/stable
echo "wireshark-common wireshark-common/install-setuid boolean false" | sudo debconf-set-selections
sudo apt update
sudo apt install -y gnupg
curl -fsSL https://pgp.mongodb.com/server-6.0.asc | \
    sudo gpg -o /usr/share/keyrings/mongodb-server-6.0.gpg --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/6.0 multiverse" | \
    sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
sudo apt update
sudo apt install -y \
    mongodb-org \
    mongodb-mongosh \
    nginx \
    python3-tk \
    tshark \
    wireshark \
    iperf3

sudo systemctl start mongod
sudo systemctl enable mongod
sudo apt install -y open5gs
sudo cp /local/repository/etc/open5gs/* /etc/open5gs/

# Bind NGAP (amf) and N3 GTP-U (upf) to this node's LAN address, and set the
# PLMN this core broadcasts (amf + nrf). With no arguments these seds are
# no-ops, reproducing core 1 (192.168.1.1, PLMN 999/99). Open5GS reads mcc/mnc
# as raw tokens, so "001"/"01" keep MCC length 3 and MNC length 2.
if [ -n "$LANIP" ]; then
    sudo sed -i "s/address: 192.168.1.1/address: $LANIP/" /etc/open5gs/amf.yaml /etc/open5gs/upf.yaml
fi
sudo sed -i -e "s/mcc: 999/mcc: $MCC/g" -e "s/mnc: 99/mnc: $MNC/g" /etc/open5gs/amf.yaml /etc/open5gs/nrf.yaml

sudo systemctl restart open5gs-mmed
sudo systemctl restart open5gs-sgwcd
sudo systemctl restart open5gs-smfd
sudo systemctl restart open5gs-amfd
sudo systemctl restart open5gs-sgwud
sudo systemctl restart open5gs-upfd
sudo systemctl restart open5gs-hssd
sudo systemctl restart open5gs-pcrfd
sudo systemctl restart open5gs-nrfd
sudo systemctl restart open5gs-ausfd
sudo systemctl restart open5gs-udmd
sudo systemctl restart open5gs-pcfd
sudo systemctl restart open5gs-nssfd
sudo systemctl restart open5gs-bsfd
sudo systemctl restart open5gs-udrd

cd $SRCDIR
wget https://raw.githubusercontent.com/open5gs/open5gs/main/misc/db/open5gs-dbctl
chmod +x open5gs-dbctl
# Subscribers for this core's PLMN: IMSI = MCC + MNC + MSIN. The Quectel SIMs
# are homed on 999/99, so on a foreign-PLMN core these entries are only usable
# by a SIM programmed for that PLMN.
K=00112233445566778899aabbccddeeff
OPC=0ed47545168eafe2c39c075829a7b61f
for MSIN in 0000000141 0000000118; do
    IMSI="${MCC}${MNC}${MSIN}"
    ./open5gs-dbctl add_ue_with_slice $IMSI $K $OPC internet 1 000001 # IMSI,K,OPC
    ./open5gs-dbctl type $IMSI 1  # APN type IPV4
done
# uv + the repo's Python helper-script dependencies (epre-sink.py --plot needs
# python3-tk for the matplotlib Tk backend, installed above).
$BINDIR/install-uv.sh

touch $SRCDIR/open5gs-setup-complete
