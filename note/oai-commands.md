# OAI N2 handover: experiment commands

Copy-paste sheet for the OAI N2 (inter-gNB) handover experiment on the
`oai-n2-handover` branch. Hostnames are for the current POWDER experiment and
change on every instantiation. The login shell on the nodes is `tcsh`; the
commands below work in it as written.

## SSH

```
# cn5g
ssh kmubassh@pc785.emulab.net
```

```
# cudu (gNB 1, X310, PCI 1)
ssh kmubassh@pc04-meb.emulab.net
```

```
# cudu2 (gNB 2, N300, PCI 3)
ssh kmubassh@pc01-meb.emulab.net
```

```
# ue1
ssh kmubassh@nuc27.emulab.net
```

Wait until every compute node shows "Finished" in the portal's Startup column
before running anything below. On `cudu` and `cudu2` the OAI build is done
when this file exists:

```
ls /var/tmp/oai-setup-complete
```

## 1. Core logs (cn5g)

```
sudo journalctl -u open5gs-amfd -u open5gs-smfd -f --output cat
```

## 2. NGAP capture (cn5g, optional, second session)

Runs until Ctrl-C.

```
/local/repository/bin/ngap-capture /tmp/oai-n2ho.pcap
```

## 3. Attenuators: only gNB 1 reaches ue1 (cudu)

```
/local/repository/bin/update-attens ru1ue1 0
```

```
/local/repository/bin/update-attens gnb2ue1 95
```

## 4. Start the gNBs (cudu AND cudu2)

Same command on both nodes; it picks gNB 1 on `cudu` and gNB 2 on `cudu2` and
stays in the foreground. Output also goes to `/tmp/gnb.log`.

```
/local/repository/bin/start-oai-gnb
```

Each gNB should print `Received NGSetupResponse from AMF`.

## 5. Attach ue1 (ue1)

### Connection manager (session 1)

Skip if it is already running (`pgrep -a quectel-CM`).

```
sudo quectel-CM -s internet -4
```

### Modem out of airplane mode (session 2)

```
/local/repository/bin/module-on.sh
```

### Ping the UPF

Keep it running through the handovers. OAI does not hand over a UE without an
established PDU session.

```
ping -i 0.2 10.45.0.1
```

## 6. Put both cells on air at similar levels (cudu)

```
/local/repository/bin/update-attens ru1ue1 5
```

```
/local/repository/bin/update-attens gnb2ue1 0
```

## 7. Hand over gNB 1 -> gNB 2 (cudu, second session)

```
/local/repository/bin/n2-handover 3
```

## 8. Hand over gNB 2 -> gNB 1 (cudu2, second session)

```
/local/repository/bin/n2-handover 1
```

Repeat 7 and 8 as often as needed.

### If n2-handover asks for the UE ID

It only finds the UE on its own when the gNB has exactly one UE context. List
them on the node serving the UE; the entry with a `MeasResultNR` line is the
connected one:

```
sudo cat /var/tmp/oai/cmake_targets/ran_build/build/nrRRC_stats.log
```

Then give the `CU UE ID` as the second argument, for example:

```
/local/repository/bin/n2-handover 3 2
```

## 9. Check the result

### Serving cell at the UE (ue1)

PCI is the field after the cell ID (`19B01` = gNB 1, PCI 1; `19C01` = gNB 2,
PCI 3). Stop `quectel-control` first if that service is running.

```
sudo sh -c 'chat -t 3 -sv "" AT OK "AT+QENG=\"servingcell\"" OK < /dev/ttyUSB2 > /dev/ttyUSB2'
```

### Handover lines in the gNB log (cudu or cudu2)

```
grep -a "Handover\|HO " /tmp/gnb.log | tail -20
```

### NGAP sequence (cn5g, after stopping the capture)

Expect HandoverRequired, HandoverRequest, HandoverRequestAcknowledge,
HandoverCommand, HandoverNotify for every handover.

```
tshark -r /tmp/oai-n2ho.pcap -Y ngap | grep -i handover
```

## 10. Stop

### ue1

```
/local/repository/bin/module-airplane.sh
```

### cudu AND cudu2

Ctrl-C in the gNB session, or from another session:

```
sudo pkill nr-softmodem
```

## If the handover stalls

The source gNB logs `send Handover Required` and nothing follows, and the AMF
log shows no `HandoverRequired`. Check the MTU of the gNB node's 192.168.1.x
interface; it must be 1500 like the core's. `start-oai-gnb` resets it at
start. The UE context is stuck after a stalled attempt: cycle the modem
(`module-airplane.sh`, then `module-on.sh`) before trying again.

```
ip -4 -o addr show | grep 192.168.1.
```

```
ip link show | grep mtu
```

## Fading with the attenuators (does not trigger a handover here)

Both gNBs are configured for A3-triggered handover, but the UE never reports
the other cell on this testbed (no PPS, cells not time aligned), so this only
moves the signal levels.

```
/local/repository/bin/handover-gnb ue1 gnb2
```
