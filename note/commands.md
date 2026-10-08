# Experiment commands

Copy-paste sheet for the OCUDU handover experiment. Hostnames are for the
current POWDER experiment and change on every instantiation.

## SSH

```
# cn5g
ssh kmubassh@pc785.emulab.net
```

```
# cudu (gNB 1, X310)
ssh kmubassh@pc04-meb.emulab.net
```

```
# cudu2 (gNB 2, N300)
ssh kmubassh@pc01-meb.emulab.net
```

```
# ue1
ssh kmubassh@nuc27.emulab.net
```

```
# ue2
ssh kmubassh@nuc22.emulab.net
```

Wait until every compute node shows "Finished" in the portal's Startup column
before running anything below.

## 1. Core logs (cn5g)

```
sudo journalctl -u open5gs-amfd -u open5gs-smfd -f --output cat
```

### Restart the core (cn5g)

Stop the gNBs first and start them again afterwards so they re-register with
the AMF.

```
sudo systemctl restart 'open5gs-*'
```

```
systemctl list-units 'open5gs-*' --no-pager
```

## 2. Intra-gNB handover (X310, PCI 1 <-> PCI 2)

### cudu: start the gNB

```
sudo numactl --membind 0 --cpubind 0 \
  /var/tmp/ocudu/build/apps/gnb/gnb -c /var/tmp/etc/ocudu/gnb_rf_x310_ho.yml
```

Note the `dl_ssb_arfcn=` value in the `Cell pci=1, ...` startup line; the
inter-gNB configs need it (section 3).

### ue1: connection manager (session 1)

```
sudo quectel-CM -s internet -4
```

### ue1: modem out of airplane mode (session 2)

```
/local/repository/bin/module-on.sh
```

### ue1: ping the UPF

```
ping 10.45.0.1
```

### cudu: hand over (second session)

```
/local/repository/bin/handover ue1 ru2
```

```
/local/repository/bin/handover ue1 ru1
```

The PCI in the gNB metrics table changes 1 -> 2 and back.

## 3. Inter-gNB handover (gNB 1 on cudu <-> gNB 2 on cudu2)

Stop the gNB from section 2 first (Ctrl-C).

### cudu AND cudu2: fill in the SSB ARFCN (once)

Set `ARFCN` to the number noted in section 2 (digits only), then run the sed.
It rewrites the whole `ssb_arfcn:` line, so it is safe to re-run.

```
ARFCN=632256
```

```
sudo sed -i "s/ssb_arfcn: .*/ssb_arfcn: $ARFCN/" /var/tmp/etc/ocudu/gnb*_inter_ho.yml
```

```
grep -n ssb_arfcn /var/tmp/etc/ocudu/gnb*_inter_ho.yml
```

### cudu AND cudu2: 5 ms SSB period (once, only on nodes deployed before the repo fix)

Without this the gNB starts but rejects its own cell (`F1 Setup Failure` in
`/tmp/gnb.log`) and no UE can attach.

```
sudo sed -i -e 's/^  pci: \([0-9]*\)$/  pci: \1\n  ssb:\n    ssb_period: 5/' /var/tmp/etc/ocudu/gnb*_inter_ho.yml
```

```
grep -n -A2 "^  pci:" /var/tmp/etc/ocudu/gnb*_inter_ho.yml
```

After starting a gNB, confirm the cell was accepted (no output means it was):

```
grep -n "F1 Setup Failure\|Invalid cell measurement" /tmp/gnb.log
```

### cudu: start gNB 1

```
sudo numactl --membind 0 --cpubind 0 \
  /var/tmp/ocudu/build/apps/gnb/gnb -c /var/tmp/etc/ocudu/gnb1_rf_x310_inter_ho.yml
```

### cudu2: start gNB 2

```
sudo /var/tmp/ocudu/build/apps/gnb/gnb -c /var/tmp/etc/ocudu/gnb2_rf_n300_inter_ho.yml
```

### ue1: attach and ping

Same as section 2 (`quectel-CM`, `module-on.sh`, `ping 10.45.0.1`).

### cudu: hand over (second session)

```
/local/repository/bin/handover-gnb ue1 gnb2
```

```
/local/repository/bin/handover-gnb ue1 gnb1
```

The UE row leaves the table on `cudu` and appears with PCI 3 on `cudu2`.

## Attenuators (cudu or cudu2, never the NUCs)

Value is 0..95; actual attenuation is 30 + value dB.

```
/local/repository/bin/atten -l
```

```
/local/repository/bin/update-attens <group> <0..95>
```

Groups: `ru1ue1`, `ru2ue1`, `ru1ue2`, `ru2ue2`, `gnb2ue1`, `gnb2ue2`, `uemon`
(all N300 paths), `all`.

### Reset to the boot state (ue1 on RU 1, everything else at max)

```
/local/repository/bin/update-attens ru1ue1 0
/local/repository/bin/update-attens ru2ue1 95
/local/repository/bin/update-attens ru1ue2 95
/local/repository/bin/update-attens ru2ue2 95
/local/repository/bin/update-attens gnb2ue1 95
/local/repository/bin/update-attens gnb2ue2 95
```

## UE modem (ue1 / ue2)

```
/local/repository/bin/module-on.sh
```

```
/local/repository/bin/module-airplane.sh
```

```
/local/repository/bin/module-off.sh
```

### Modem requests the wrong slice (AMF log: `Cannot find Requested NSSAI`, `Registration reject [62]`)

The modem keeps slice settings from earlier experiments. Show what it holds:

```
sudo sh -c "chat -t 3 -sv '' AT OK 'AT+C5GNSSAIRDP=3' OK < /dev/ttyUSB2 > /dev/ttyUSB2"
```

Set the default slice to SST 1 / SD 1, then cycle the modem:

```
sudo bash -c 'chat -t 3 -sv "" AT OK "AT+C5GNSSAI=4,\"01.000001\"" OK < /dev/ttyUSB2 > /dev/ttyUSB2'
```

```
/local/repository/bin/module-airplane.sh
```

```
/local/repository/bin/module-on.sh
```

These drive the AT port directly and conflict with a running `quectel-control`
service. With the service up, use the `uv run` commands below instead.

```
/local/repository/bin/ue-services start
```

```
/local/repository/bin/ue-services status
```

```
/local/repository/bin/ue-services stop
```

```
sudo systemctl start quectel-control
```

```
cd /local/repository && uv run bin/quectel_control.py up
```

```
cd /local/repository && uv run bin/quectel_control.py airplane
```

```
cd /local/repository && uv run bin/quectel_control.py scan
```

```
cd /local/repository && uv run bin/ue_app.py
```

```
cd /local/repository && uv run bin/ue_metrics.py
```

## Metrics and logs (cudu / cudu2)

```
cd /local/repository && uv run bin/metrics-receiver.py --output metrics.jsonl
```

```
cd /local/repository && uv run bin/rrm-policy-set.py -h
```

```
tail -f /tmp/gnb.log
```

## Traffic

```
# cn5g
iperf3 -s
```

```
# ue1: uplink
iperf3 -c 10.45.0.1 -t 30
```

```
# ue1: downlink
iperf3 -c 10.45.0.1 -t 30 -R
```

## X310 FPGA mismatch (cudu)

Only if the gNB fails with `RFNoC protocol mismatch between SW and HW`.

```
sudo uhd_images_downloader -t x3xx
```

```
uhd_image_loader --args="type=x300,addr=192.168.30.2,fpga=XG"
```

Power cycle `sdru-sdr` from the portal, wait about a minute, then:

```
uhd_usrp_probe --args addr=192.168.30.2
```
