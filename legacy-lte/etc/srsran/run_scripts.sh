#!/bin/bash
sudo chmod +x epc_fake.sh
sudo chmod +x epc_real.sh
sudo chmod +x enb_fake.sh
sudo chmod +x enb_real.sh
sudo chmod +x ue.sh
sudo ./epc_fake.sh
sudo ./epc_real.sh
sudo ./enb_fake.sh
sudo ./enb_real.sh
sudo ./ue.sh
