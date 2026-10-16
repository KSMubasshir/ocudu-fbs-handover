#!/bin/bash
set -ex
# deploy-oai-lte.sh <commit hash>
# Build the OAI LTE eNB (lte-softmodem) and install the eNB configs. The LTE
# twin of deploy-oai.sh (which builds the 5G gNB, nr-softmodem). Same OAI
# checkout and vendored UHD 4.10 debs; only the build target and configs differ.
COMMIT_HASH=$1
BINDIR=`dirname $0`
ETCDIR=/local/repository/etc
DEBDIR=/local/repository/debs
source $BINDIR/common.sh

if [ -f $SRCDIR/oai-setup-complete ]; then
  echo "setup already ran; not running again"
  exit 0
fi

# install UHD 4.10 debs vendored in the repo (Ettus PPA moved on to 4.11).
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $DEBDIR/*.deb

sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git \
  iperf3 \
  libboost-all-dev \
  netcat-openbsd \
  numactl

# uv + the repo's Python helper-script dependencies (shared with the UE nodes).
$BINDIR/install-uv.sh

cd $SRCDIR
git clone $OAI_REPO oai
cd oai
git checkout $COMMIT_HASH

# LTE FBS misbehaviour for eNB 2 (the false base station), analogous to the 5G
# patches/oai-fbs-misbehavior.patch: OAI_FBS_MODE selects how the FBS mistreats
# the UE (reject / ignore RRC / drop the NAS Attach). No-op when OAI_FBS_MODE is
# unset, so the home eNB 1 built from the same tree behaves normally. Optional:
# the lure and connected-mode tests do not need it; only the DoS scenarios do.
PATCH=/local/repository/patches/oai-lte-fbs-misbehavior.patch
if [ -f $PATCH ]; then
  echo "applying LTE FBS patch $PATCH"
  git apply --verbose $PATCH
fi

cd cmake_targets
./build_oai -I
./build_oai --ninja --eNB -w USRP

echo configuring enb...
mkdir -p $SRCDIR/etc/oai
cp -r $ETCDIR/oai-lte/* $SRCDIR/etc/oai/
echo configuring enb... done.

touch $SRCDIR/oai-setup-complete
