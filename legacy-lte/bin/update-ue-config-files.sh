#!/bin/sh

set -x

SETUPDIR=`dirname $0`

. $SETUPDIR/setup-common.sh

[ ! -d $OURDIR ] && mkdir -p $OURDIR

if [ -f $OURDIR/update-ue-config-files-done ]; then
    echo "update-ue-config-files already ran; not running again"
    exit 0
fi

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
[ -z "$TX_GAIN" ] && TX_GAIN=${DEF_TX_GAIN}
[ -z "$RX_GAIN" ] && RX_GAIN=${DEF_RX_GAIN}
[ -z "$DL_FREQ" ] && DL_FREQ=3435e6
[ -z "$UL_FREQ" ] && UL_FREQ=3410e6
[ -z "$DL_EARFCN" ] && DL_EARFCN=
[ -z "$FREQ_OFFSET" ] && FREQ_OFFSET=0
[ -z "$DEFKEY" ] && DEFKEY=00112233445566778899aabbccddeeff

sudo apt-get -y update \
    && sudo apt-get -y install crudini

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
sudo crudini --set /etc/srslte/ue.conf \
    rf dl_freq "$DL_FREQ"
sudo crudini --set /etc/srslte/ue.conf \
    rf ul_freq "$UL_FREQ"
sudo crudini --set /etc/srslte/ue.conf \
    rf tx_gain "$TX_GAIN"
sudo crudini --set /etc/srslte/ue.conf \
    rf rx_gain "$RX_GAIN"

# imsi (15 h),imei (15 h),key (32 h)
imsi=`echo "$1" | cut -d, -f1`
imei=`echo "$1" | cut -d, -f2`
key=`echo "$1" | cut -d, -f3`
[ -z "$key" ] && key="$DEFKEY"

sudo crudini --set /etc/srslte/ue.conf \
    usim algo xor
sudo crudini --set /etc/srslte/ue.conf \
    usim k "$key"
sudo crudini --set /etc/srslte/ue.conf \
    usim imsi "$imsi"
sudo crudini --set /etc/srslte/ue.conf \
    usim imei "$imei"

sudo crudini --set /etc/srslte/ue.conf \
    nas force_imsi_attach true

touch $OURDIR/update-ue-config-files-done
