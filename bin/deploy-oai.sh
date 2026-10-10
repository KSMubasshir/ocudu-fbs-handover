set -ex
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
# build_oai -I is run without -w USRP below so it does not install another UHD.
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $DEBDIR/*.deb

sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git \
  iperf3 \
  netcat-openbsd \
  numactl

# uv + the repo's Python helper-script dependencies (shared with the UE nodes).
$BINDIR/install-uv.sh

cd $SRCDIR
git clone $OAI_REPO oai
cd oai
git checkout $COMMIT_HASH

cd cmake_targets
./build_oai -I
# telnetsrv carries the "ci trigger_n2_ho" command used to force a handover
./build_oai --ninja --gNB -w USRP --build-lib telnetsrv

echo configuring nodeb...
mkdir -p $SRCDIR/etc/oai
cp -r $ETCDIR/oai/* $SRCDIR/etc/oai/
echo configuring nodeb... done.

touch $SRCDIR/oai-setup-complete
