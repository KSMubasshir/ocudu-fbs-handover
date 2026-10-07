#!/bin/bash
cd /var/tmp/SRSRAN/build/srsenb/src/
sudo cp ../../../srsenb/enb.conf.example enb.conf
sudo cp ../../../srsenb/rr.conf.example rr.conf
sudo cp ../../../srsenb/rb.conf.example rb.conf
sudo cp ../../../srsenb/sib.conf.example sib.conf
sudo cp ../../../srsenb/sib.conf.mbsfn.example sib.conf.mbsfn
#sudo ./srsenb enb.conf