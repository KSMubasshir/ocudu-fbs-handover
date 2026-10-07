set -ex
COMMIT_HASH=$1
PHY_TAP=$2   # "phytap" to build the upstream PHY tap plugin (UL EPRE ZMQ tap)
BINDIR=`dirname $0`
ETCDIR=/local/repository/etc
DEBDIR=/local/repository/debs
source $BINDIR/common.sh

if [ -f $SRCDIR/ocudu-setup-complete ]; then
  echo "setup already ran; not running again"
  exit 0
fi

# install UHD 4.10 debs vendored in the repo (Ettus PPA moved on to 4.11)
sudo apt-get update
sudo apt-get install -y --no-install-recommends $DEBDIR/*.deb

sudo apt-get install -y \
  cmake \
  make \
  gcc \
  g++ \
  iperf3 \
  pkg-config \
  libboost-dev \
  libfftw3-dev \
  libmbedtls-dev \
  libsctp-dev \
  libyaml-cpp-dev \
  libgtest-dev \
  libzmq3-dev \
  numactl \
  ppp

# uv + the repo's Python helper-script dependencies (shared with the UE nodes).
$BINDIR/install-uv.sh

cd $SRCDIR
git clone $OCUDU_REPO
cd ocudu
git checkout $COMMIT_HASH

if [ "$PHY_TAP" = "phytap" ]; then
  # OCUDU's top-level CMake picks up any plugins/*/CMakeLists.txt automatically.
  # The plugin is pinned to a specific upstream commit and patched so the EPRE
  # tap emits full messages for quiet (unallocated) UL slots.
  mkdir -p plugins
  git clone $PHY_TAP_REPO plugins/phy_tap_plugin_example
  git -C plugins/phy_tap_plugin_example checkout $PHY_TAP_COMMIT_HASH
  git -C plugins/phy_tap_plugin_example apply $ETCDIR/phy_tap/437e5356-compute_epre_quiet_dims.patch
fi

mkdir build
cd build
cmake -DCMAKE_CXX_FLAGS="${CMAKE_CXX_FLAGS} -Wno-error=switch" ../
make -j $(nproc)

echo configuring nodeb...
mkdir -p $SRCDIR/etc/ocudu
cp -r $ETCDIR/ocudu/* $SRCDIR/etc/ocudu/
LANIF=`ip r | awk '/192\.168\.1\.0/{print $3}'`
if [ ! -z $LANIF ]; then
  LANIP=`ip r | awk '/192\.168\.1\.0/{print $NF}'`
  echo LAN IFACE is $LANIF IP is $LANIP.. updating nodeb config
  find $SRCDIR/etc/ocudu/ -type f -exec sed -i "s/LANIP/$LANIP/" {} \;
  IPLAST=`echo $LANIP | awk -F. '{print $NF}'`
  find $SRCDIR/etc/ocudu/ -type f -exec sed -i "s/GNBID/$IPLAST/" {} \;
else
  echo No LAN IFACE.. not updating nodeb config
fi
echo configuring nodeb... done.

touch $SRCDIR/ocudu-setup-complete
