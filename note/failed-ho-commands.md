# Failed handover to an unknown cell: experiment commands

Branch `oai-failed-handover`. gNB 1 (`cudu` -> core 1 `cn5g`, home PLMN 999/99)
is told to measure gNB 2's carrier so the UE treats gNB 2 as a handover
candidate, but gNB 1 holds **no neighbour relation for gNB 2's PCI (3)**. This
is the spec-realistic "unknown cell" case (TS 38.300): a gNB hands over only to
cells in its neighbour relation table, and OAI has no `reportCGI` fallback, so a
reported PCI with no relation cannot be resolved to a target and the handover is
refused at the source -- nothing reaches the core. gNB 2 (`cudu2` -> core 2
`cn5g2`, foreign 001/01) is a real but unrelated network on its own carrier
(3319.68 MHz).

The measure-only neighbour config
([etc/oai/neighbour-config-measonly.conf](../etc/oai/neighbour-config-measonly.conf))
puts gNB 2's carrier (ARFCN 621312) into the UE's measurement config via one
*legitimate* same-operator sister cell (PCI 500, not on air in this lab). gNB
2's real cell (PCI 3, PLMN 001/01 on core 2) is deliberately absent, so a report
for PCI 3 hits "no such neighbour in configuration".

Hostnames change per POWDER instantiation; set them in `hosts.env` (needs
`CN5G2` too). The login shell on the nodes is `tcsh`.

## Whole run from your machine

```
bin/run-failed-ho-exp
```

Installs the gNB configs, starts both gNBs, attaches ue1 to gNB 1, raises
gNB 2, forces a handover toward gNB 2's PCI, and copies the trace to
`traces/failed-ho-<date>-<time>/` (core 1 NGAP pcap + text, AMF log, both gNB
logs, UE serving cell, ping). The summary shows gNB 1 refusing the handover and
that no `HandoverRequired` was sent.

## By hand

### Start the gNBs (cudu and cudu2)

```
/local/repository/bin/start-oai-gnb
```

gNB 1's log prints only the legitimate sister cell on the measured frequency,
not gNB 2:
`Neighbour[0]: cellId 105729, PLMN 999.99, gNB 413, PCI 500, ... SSB ARFCN 621312`.

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

### Force a handover toward gNB 2's PCI (cudu)

The UE id is the `CU UE ID` in
`/var/tmp/oai/cmake_targets/ran_build/build/nrRRC_stats.log`. 3 is gNB 2's PCI.

```
echo ci trigger_n2_ho 3,<ue id> | nc -w 2 127.0.0.1 9090
```

### Read the result

```
# cudu: gNB 1 cannot resolve PCI 3 and refuses
grep -a "could not find neighbour cell with PCI\|no such neighbour" /tmp/gnb.log | tail

# cn5g: no handover messages at all
sudo tshark -r /tmp/ngap.pcap -Y ngap
```

Expected: gNB 1 `N2 HO trigger failed for UE <id>: could not find neighbour cell with PCI=3`;
core 1 NGAP shows **no** `HandoverRequired` (the handover never left gNB 1); the
UE stays on gNB 1 (`AT+QENG="servingcell"` keeps showing 999,99 PCI 1) and the
ping is uninterrupted. If a UE that does inter-frequency reporting is used, the
spontaneous path logs the same cause: `received A3 event for stronger neighbor
PCI 3, but no such neighbour in configuration`.

## Collecting data per node

The whole run above (`bin/run-failed-ho-exp`) runs from a machine with SSH
access to every node and copies all traces to `traces/`. If instead you run the
steps by hand while logged into the nodes, run `bin/collect-node` on each node
afterwards to bundle that node's own data:

```
# on cudu, cudu2, cn5g, cn5g2, ue1 -- each gathers only its own data
/local/repository/bin/collect-node
```

It writes `/var/tmp/collect-<host>-<time>/` and a `.tar.gz`, and prints the
`scp` line to fetch it. gNB nodes get the gNB log, RRC/MAC/L1 stats and the
config; core nodes get the AMF/SMF/UPF log, the PLMN and any NGAP pcap; UE nodes
get the modem serving/neighbour cells and ping logs. It does not reach other
nodes (the experiment nodes cannot SSH to each other), so run it on each one.

## Why the handover is forced, not UE-initiated

On this testbed the Quectel does not emit the measurement report: connected to
gNB 1, its `AT+QENG="neighbourcell"` list stays empty and no RRC
`measurementReport` arrives, same carrier or different (no PPS, COTS modem). So
the handover is forced from gNB 1's console as a stand-in for the UE's request.
The outcome is the same either way: gNB 1 has no relation for PCI 3 and cannot
prepare a handover.

## Model A vs the stale-relation variant

This is model A (unknown cell): gNB 1 holds no relation for gNB 2, so the
handover fails at the source with nothing on the N2 wire -- the most realistic
rendering of "the serving network has no information about the target". The
earlier phantom variant (a *wrong* relation to a fabricated NCGI, which makes
gNB 1 send a `HandoverRequired` the core then rejects) modelled a stale/
misconfigured neighbour relation or PCI confusion instead; it was replaced by
this one. To recreate it, add gNB_ID/nr_cellid/plmn/physical_cellId=3 for a
target core 1 cannot resolve.
