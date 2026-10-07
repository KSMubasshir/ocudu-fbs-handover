#!/bin/bash
cd /var/tmp
git clone https://github.com/KSMubasshir/SRSRAN
cd SRSRAN/
mkdir build
cd build
sudo cmake ../
sudo make -j `nproc`