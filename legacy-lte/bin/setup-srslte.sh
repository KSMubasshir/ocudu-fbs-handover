#!/bin/sh

set -x

SETUPDIR=`dirname $0`

. $SETUPDIR/setup-common.sh

if [ ! -d $OURDIR ]; then
    mkdir -p $OURDIR
fi

if [ -f $OURDIR/setup-srslte-done ]; then
    echo "setup-srslte already ran; not running again"
    exit 0
fi

cd $OURDIR

$SETUPDIR/setup-e2-bindings.sh

$SETUPDIR/setup-asn1c.sh

#logtstart "srslte"

#
# srsLTE build
#
cd $OURDIR

$SUDO apt-get -y update
$SUDO apt-get install -y \
    autoconf cmake libfftw3-dev libmbedtls-dev libboost-program-options-dev \
    libconfig++-dev libsctp-dev libzmq3-dev iperf3

git clone https://gitlab.flux.utah.edu/powderrenewpublic/srslte-ric
cd srslte-ric
mkdir -p build
cd build
cmake ../ \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DRIC_GENERATED_E2AP_BINDING_DIR=$OURDIR/E2AP-v02.03 \
    -DRIC_GENERATED_E2SM_KPM_BINDING_DIR=$OURDIR/E2SM-KPM \
    -DRIC_GENERATED_E2SM_NI_BINDING_DIR=$OURDIR/E2SM-NI \
    -DRIC_GENERATED_E2SM_GNB_NRT_BINDING_DIR=$OURDIR/E2SM-GNB-NRT
NCPUS=`grep proc /proc/cpuinfo | wc -l`
if [ -n "$NCPUS" ]; then
    make -j$NCPUS
else
    make
fi
$SUDO make install
$SUDO ldconfig
if [ -d /etc/srslte ]; then
    $SUDO rm -rf /etc/srslte
fi
$SUDO ./srslte_install_configs.sh service

#logtend "srslte"
touch $OURDIR/setup-srslte-done
