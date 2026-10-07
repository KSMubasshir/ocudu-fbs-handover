#!/bin/bash
cd /var/tmp/SRSRAN/build/srsepc/src/
sudo cp ../../../srsepc/epc.conf.example epc.conf
sudo cp ../../../srsepc/user_db.csv.example user_db.csv
sudo cp ../../../srsepc/mbms.conf.example mbms.conf
#sudo ./srsepc epc.conf