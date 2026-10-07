#!/bin/sh

set -x

SETUPDIR=`dirname $0`

. $SETUPDIR/setup-common.sh

[ ! -d $OURDIR ] && mkdir -p $OURDIR

if [ -f $OURDIR/update-enb-config-files-done ]; then
    echo "update-enb-config-files already ran; not running again"
    exit 0
fi

ENB_ID="$1"
shift

uhd_find_devices | grep -q -i x310
if [ $? -eq 0 ]; then
    DEF_TX_GAIN=28
    DEF_RX_GAIN=25
else
    DEF_TX_GAIN=90
    DEF_RX_GAIN=70
fi

[ -z "$MCC" ] && MCC="001"
[ -z "$MNC" ] && MNC="01"
[ -z "$ENB_ID" ] && ENB_ID="0x001"
[ -z "$PRB" ] && PRB=50
[ -z "$TX_GAIN" ] && TX_GAIN=${DEF_TX_GAIN}
[ -z "$RX_GAIN" ] && RX_GAIN=${DEF_RX_GAIN}
[ -z "$DL_FREQ" ] && DL_FREQ=3435e6
[ -z "$UL_FREQ" ] && UL_FREQ=3410e6
[ -z "$DL_EARFCN" ] && DL_EARFCN=
[ -z "$DEFKEY" ] && DEFKEY=00112233445566778899aabbccddeeff
[ -z "$DL_MASK" ] && DL_MASK=0x0
[ -z "$UL_MASK" ] && UL_MASK=0x0
[ -z "$SLICER_ENABLE" ] && SLICER_ENABLE=1
[ -z "$SLICER_WORKSHARE" ] && SLICER_WORKSHARE=1

sudo apt-get -y update \
    && sudo apt-get -y install crudini

sudo crudini --set /etc/srslte/epc.conf \
    spgw sgi_if_addr 192.168.0.1
sudo crudini --set /etc/srslte/epc.conf \
    mme mcc "$MCC"
sudo crudini --set /etc/srslte/epc.conf \
    mme mnc "$MNC"
sudo crudini --del /etc/srslte/epc.conf \
    mme dnsaddr

sudo crudini --set /etc/srslte/enb.conf \
    enb enb_id "$ENB_ID"
sudo crudini --set /etc/srslte/enb.conf \
    enb mcc "$MCC"
sudo crudini --set /etc/srslte/enb.conf \
    enb mnc "$MNC"
sudo crudini --set /etc/srslte/enb.conf \
    enb n_prb "$PRB"
if [ -n "$DL_EARFCN" ]; then
    sudo crudini --set /etc/srslte/enb.conf \
        rf dl_earfcn "$DL_EARFCN"
else
    sudo crudini --del /etc/srslte/enb.conf \
        rf dl_earfcn
fi
if [ -n "$UL_EARFCN" ]; then
    sudo crudini --set /etc/srslte/enb.conf \
        rf ul_earfcn "$UL_EARFCN"
else
    sudo crudini --del /etc/srslte/enb.conf \
        rf ul_earfcn
fi
sudo crudini --set /etc/srslte/enb.conf \
    rf dl_freq "$DL_FREQ"
sudo crudini --set /etc/srslte/enb.conf \
    rf ul_freq "$UL_FREQ"
sudo crudini --set /etc/srslte/enb.conf \
    rf tx_gain "$TX_GAIN"
sudo crudini --set /etc/srslte/enb.conf \
    rf rx_gain "$RX_GAIN"

LOCALRICADDR=`ip -br a | grep '10\.254\.254' | awk '{print $3}' | cut -d/ -f1`
if [ -n "$LOCALRICADDR" ]; then
    sudo crudini --set /etc/srslte/enb.conf \
        ric agent.local_ipv4_addr "$LOCALRICADDR"
fi
sudo crudini --set /etc/srslte/enb.conf \
    ric agent.local_port 52525
sudo crudini --set /etc/srslte/enb.conf \
    ric agent.log_level debug
sudo crudini --set /etc/srslte/enb.conf \
    log filename stdout
sudo crudini --set /etc/srslte/enb.conf \
    slicer enable $SLICER_ENABLE
sudo crudini --set /etc/srslte/enb.conf \
    slicer workshare $SLICER_WORKSHARE
sudo crudini --set /etc/srslte/enb.conf \
    zylinium dl_mask $DL_MASK
sudo crudini --set /etc/srslte/enb.conf \
    zylinium ul_mask $UL_MASK

# idx,imsi (15 h),key (32 h),ipaddr
while [ -n "$1" ]; do
    idx=`echo "$1" | cut -d, -f1`
    imsi=`echo "$1" | cut -d, -f2`
    imei=`echo "$1" | cut -d, -f3`
    ipaddr=`echo "$1" | cut -d, -f4`
    [ -z "$ipaddr" ] && ipaddr="dynamic"
    key=`echo "$1" | cut -d, -f5`
    [ -z "$key" ] && key="$DEFKEY"
    shift

    sudo sed -i -nre "s/^(ue${idx},.*)\$/#\\1/" /etc/srslte/user_db.csv
    echo "ue${idx},xor,${imsi},${key},opc,63bfa50ee6523365ff14c1f45f88737d,9001,000000001234,7,${ipaddr}" | sudo tee -a /etc/srslte/user_db.csv
done

touch $OURDIR/update-enb-config-files-done
