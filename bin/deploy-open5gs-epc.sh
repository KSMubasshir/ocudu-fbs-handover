#!/bin/bash
set -ex
# deploy-open5gs-epc.sh [<mcc> <mnc> [<tac>]]
# Install Open5GS as a 4G/LTE EPC and provision the two subscribers. The LTE
# twin of deploy-open5gs.sh (which binds the 5G AMF/UPF). Open5GS installs the
# EPC daemons (MME, SGW-C/U, PGW via SMF/UPF, HSS, PCRF) and the 5GC daemons
# from the same package, so this script installs everything and then binds the
# 4G control/user plane the eNB needs:
#   - MME S1AP server -> this node's 192.168.1.x (the eNB's S1-C endpoint)
#   - SGW-U GTP-U server -> this node's 192.168.1.x (the eNB's S1-U endpoint)
#   - MME gummei/TAI PLMN + TAC
# Without arguments this is the home EPC (epc, PLMN 999/99, TAC 1). With
# <mcc> <mnc> [<tac>] it is the FBS EPC (epc2); give the digits exactly as in
# the PLMN, e.g. "999 99", and a different <tac> (2) so an idle UE that
# reselects to the FBS performs a Tracking Area Update / attach on this core.
BINDIR=`dirname $0`
source $BINDIR/common.sh

MCC=${1:-999}
MNC=${2:-99}
TAC=${3:-1}
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

# 4G control/user plane the eNB connects to. Bind only the S1AP server (MME)
# and the GTP-U server (SGW-U) to the node's LAN address; the intra-core
# loopback endpoints (GTP-C, PFCP, SBI, metrics) are left as-is so the EPC's
# own daemons keep talking to each other on 127.0.0.x.
if [ -n "$LANIP" ]; then
    # MME S1AP server (first "address:" in the s1ap: .. gtpc: block).
    sudo sed -i "/s1ap:/,/gtpc:/ s/address: 127.0.0.2/address: $LANIP/" /etc/open5gs/mme.yaml
    # SGW-U GTP-U server (the gtpu: block at the end of sgwu.yaml), leaving the
    # PFCP endpoint on loopback so SGW-C's PFCP client still reaches it.
    sudo sed -i "/gtpu:/,\$ s/address: 127.0.0.6/address: $LANIP/" /etc/open5gs/sgwu.yaml
fi
# PLMN this EPC serves (MME gummei + TAI). The repo mme.yaml ships 999/70; set
# it to MCC/MNC so it matches the provisioned subscribers and the eNB broadcast.
sudo sed -i -e "s/mcc: 999/mcc: $MCC/g" -e "s/mnc: 70/mnc: $MNC/g" /etc/open5gs/mme.yaml
# Tracking area this EPC serves (MME tai tac). The eNB's tracking_area_code
# must match, or S1 Setup / attach is rejected.
sudo sed -i -e "s/tac: 1/tac: $TAC/" /etc/open5gs/mme.yaml

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
# Subscribers for this EPC's PLMN: IMSI = MCC + MNC + MSIN. The Quectel SIMs are
# homed on 999/99; the FBS EPC holds the same subscribers so the lured UE can
# (re)attach on it. open5gs-dbctl writes the shared HSS/UDR subscriber DB.
K=00112233445566778899aabbccddeeff
OPC=0ed47545168eafe2c39c075829a7b61f
for MSIN in 0000000141 0000000118; do
    IMSI="${MCC}${MNC}${MSIN}"
    ./open5gs-dbctl add_ue_with_slice $IMSI $K $OPC internet 1 000001 # IMSI,K,OPC
    ./open5gs-dbctl type $IMSI 1  # APN type IPV4
done
$BINDIR/install-uv.sh

touch $SRCDIR/open5gs-setup-complete
