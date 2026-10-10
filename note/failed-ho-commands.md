# Failed handover to a phantom neighbour: experiment commands

Branch `oai-failed-handover`. gNB 1 (`cudu` -> core 1 `cn5g`, home PLMN 999/99)
is told to treat gNB 2's cell as a handover candidate via a phantom neighbour
([etc/oai/neighbour-config-phantom.conf](../etc/oai/neighbour-config-phantom.conf)):
it advertises gNB 2's real carrier (SSB ARFCN 621312) and PCI (3), but the
target identity is fake (gNB 420, cell 107521, gNB 1's own PLMN 999/99) and
core 1 serves no such cell. A handover toward it is sent to core 1 as NGAP
`HandoverRequired`, core 1 rejects it (`cannot find target gNB-id`), and the UE
stays on gNB 1. gNB 2 (`cudu2` -> core 2 `cn5g2`, foreign 001/01) is a real but
unrelated network on its own carrier (3319.68 MHz).

Hostnames change per POWDER instantiation; set them in `hosts.env` (needs
`CN5G2` too). The login shell on the nodes is `tcsh`.

## Whole run from your machine

```
bin/run-failed-ho-exp
```

Installs the gNB configs, starts both gNBs, attaches ue1 to gNB 1, raises
gNB 2, forces the handover toward the phantom target, and copies the trace to
`traces/failed-ho-<date>-<time>/` (core 1 NGAP pcap + text, AMF log, both gNB
logs, UE serving cell, ping). The summary prints the `HandoverRequired`, the
core's rejection, and the UE's serving cell afterwards.

## By hand

### Start the gNBs (cudu and cudu2)

```
/local/repository/bin/start-oai-gnb
```

gNB 1's log should print the phantom neighbour:
`Neighbour[0]: cellId 107521, PLMN 999.99, gNB 420, PCI 3, ... SSB ARFCN 621312`.

### Attach ue1 to gNB 1, then raise gNB 2 (cudu, ue1)

```
# cudu
/local/repository/bin/update-attens ru1ue1 0
/local/repository/bin/update-attens gnb2ue1 95
```

```
# ue1
sudo quectel-CM -s internet -4
/local/repository/bin/module-on.sh
ping 10.45.0.1
```

```
# cudu: bring gNB 2's cell up at ue1
/local/repository/bin/update-attens gnb2ue1 0
```

### Capture NGAP on core 1 (cn5g, second session)

```
/local/repository/bin/ngap-capture /tmp/ngap.pcap
```

### Force the handover toward the phantom target (cudu)

The UE id is the `CU UE ID` in
`/var/tmp/oai/cmake_targets/ran_build/build/nrRRC_stats.log`. 3 is gNB 2's PCI.

```
echo ci trigger_n2_ho 3,<ue id> | nc -w 2 127.0.0.1 9090
```

### Read the result

```
# cudu: gNB 1 sends HandoverRequired for the phantom target
grep -aE "trigger_n2|Handover" /tmp/gnb.log | tail

# cn5g: the AMF cannot resolve it
sudo tshark -r /tmp/ngap.pcap -Y ngap
sudo journalctl -u open5gs-amfd --since "-1 min" -o cat | grep -i handover
```

Expected: gNB 1 `Handover Preparation: send Handover Required (target gNB ID=420, PCI=3)`;
core 1 NGAP `HandoverRequired` then `ErrorIndication [Cause: Protocol=semantic-error]`;
AMF `ERROR: Handover required : cannot find target gNB-id[0x1a4]`; the UE stays
on gNB 1 (`AT+QENG="servingcell"` keeps showing 999,99 PCI 1) and the ping is
uninterrupted.

## Why the handover is forced, not UE-initiated

The intent is that the UE reports gNB 2 as a candidate and asks to be handed
over. The phantom neighbour configures the UE to measure gNB 2's carrier, but
on this testbed the Quectel does not emit the report: connected to gNB 1, its
`AT+QENG="neighbourcell"` list stays empty and no RRC `measurementReport`
arrives, on the same carrier or a different one (no PPS, COTS modem). So the
handover is forced from gNB 1's console as a stand-in for the UE's request. The
failure at the core is the same either way: the serving core has no information
about the target and rejects it.

## Changing the phantom target

Edit [etc/oai/neighbour-config-phantom.conf](../etc/oai/neighbour-config-phantom.conf):
keep `physical_cellId` and `absoluteFrequencySSB` equal to gNB 2's real cell
(so the UE would measure it), and keep `gNB_ID`/`nr_cellid`/`plmn` as values
core 1 does not serve (so the handover fails). Using gNB 2's real identity
instead would make it resolvable only if gNB 2 were on core 1, which it is not.
