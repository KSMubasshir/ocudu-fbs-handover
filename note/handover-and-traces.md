# Inter-gNB handover with NGAP and measurement report collection

One run from start to finish: force a handover between gNB 1 (cudu) and gNB 2
(cudu2), capture the NGAP messages on the core, and extract the UE measurement
reports (MRs) from the gNB logs. Tested 2026-10-08 with ue1.

Why the handover is forced from the console, and what to do when a step fails,
is in [troubleshooting.md](troubleshooting.md) sections 6 and 7. Hostnames are
in [commands.md](commands.md).

## The whole run in one command

From your own machine, in the repo:

```
bin/run-inter-gnb-exp -n 4
```

It does every step below over SSH and copies the results into
`traces/<date>-<time>/`: `ngap.pcap`, `meas-gnb1.csv`, `meas-gnb2.csv`,
`ping-ue1.txt`, and both gNB logs and consoles. It ends with a summary and
exits non-zero if not every handover completed. A run with four handovers
takes about two minutes.

- Put the current hostnames in [hosts.env](../hosts.env) first; they change
  with every POWDER experiment.
- `-n` is the number of handovers (default 2), `-i` the seconds between them
  (default 10), `-o` the output directory.
- It restarts both gNBs at the start and stops them at the end, so the logs
  hold exactly this run and are completely written. Start them again by hand
  (step 1) if you want to continue afterwards.
- On a node without the OCUDU patch it applies the patch and rebuilds first.
  That path has not been exercised yet; both current nodes were already
  patched.

The rest of this note is the same run by hand.

## Before you start

- Both gNB nodes run OCUDU with the patch from troubleshooting.md section 7.
  Without it the first handover works and the second one drops the UE.
- The login shell on the nodes is csh. The commands below work as written.

## 1. cudu and cudu2: start the gNBs in tmux

tmux keeps the gNB console alive when the SSH session ends; you need the
console to type the handover command.

```
tmux new-session -d -s gnb /local/repository/bin/start-inter-gnb
```

```
tmux attach -t gnb
```

Wait for `==== gNB started ===` on both. Detach with Ctrl-b d.

## 2. cudu: put ue1 on gNB 1

```
/local/repository/bin/update-attens ru1ue1 0
/local/repository/bin/update-attens gnb2ue1 95
```

## 3. ue1: attach and ping

```
tmux new-session -d -s cm 'sudo quectel-CM -s internet -4'
```

```
/local/repository/bin/module-airplane.sh
/local/repository/bin/module-on.sh
```

```
ping -i 0.1 10.45.0.1
```

A row with PCI 1 and a CQI value appears in the metrics table on cudu. Rows
with `n/a` that come and go every 10 seconds are ue2 being rejected
(troubleshooting.md section 5); ignore them.

## 4. cn5g: start the NGAP capture

Start it before the handover. It runs until Ctrl-C.

```
/local/repository/bin/ngap-capture /tmp/ngap.pcap
```

## 5. cudu: bring both cells to similar levels

```
/local/repository/bin/update-attens ru1ue1 5
/local/repository/bin/update-attens gnb2ue1 0
```

This gives about -83 dBm from gNB 1 and -81 dBm from gNB 2 at ue1. Keep them
within a few dB of each other; a serving cell much weaker than the other one
loses the UE.

## 6. Hand over

Type into the console of the gNB that is serving the UE. `<rnti>` is the second
column of ue1's row in that gNB's metrics table, without `0x`. It is different
after every handover.

```
# cudu console: gNB 1 -> gNB 2
ho 1 <rnti> 3
```

```
# cudu2 console: gNB 2 -> gNB 1
ho 3 <rnti> 1
```

The console answers `Handover triggered for UE with pci=1 rnti=0x4614 to pci=3.`
The row disappears from one table and appears in the other with the new PCI
and a new RNTI. The ping keeps running; in the test no ping was lost.

Wait a few seconds between handovers so the new row has shown up.

## 7. cn5g: stop the capture and read it

Ctrl-C in the capture session, then:

```
tshark -r /tmp/ngap.pcap -Y ngap
```

One successful handover is these nine messages, about 0.6 s from first to last
(192.168.1.1 is the AMF, .2 is gNB 1, .3 is gNB 2):

| From | To | Message |
|------|----|---------|
| source gNB | AMF | `HandoverRequired` |
| AMF | target gNB | `HandoverRequest` |
| target gNB | AMF | `HandoverRequestAcknowledge` |
| AMF | source gNB | `HandoverCommand` |
| source gNB | AMF | `UplinkRANStatusTransfer` |
| AMF | target gNB | `DownlinkRANStatusTransfer` |
| target gNB | AMF | `HandoverNotify` |
| AMF | source gNB | `UEContextReleaseCommand` (cause `successful-handover`) |
| source gNB | AMF | `UEContextReleaseComplete` |

A failed handover shows `HandoverFailure` and `HandoverPreparationFailure`
instead.

Only the handover messages:

```
tshark -r /tmp/ngap.pcap -Y ngap | grep -i "handover\|RANStatus\|UEContextRelease"
```

## 8. cudu and cudu2: extract the measurement reports

Run on both nodes. A UE's reports are in the log of the gNB that was serving it
at the time, so one handover splits them across the two files.

```
/local/repository/bin/meas-reports.py -o /tmp/meas.csv
```

Columns: `time, ue, rnti, meas_id, cell, pci, rsrp_dbm, rsrq_db, sinr_db`.
`cell` is `serving` or `neighbour`. There is one row per reported cell, every
480 ms per UE:

```
2026-10-08T15:01:22.290020,2,0x4605,1,serving,3,-80,-10.0,23.5
```

The raw reports, one JSON object per line:

```
/local/repository/bin/meas-reports.py --jsonl > /tmp/meas.jsonl
```

What to expect:

- Time is UTC. `ue` and `rnti` change at every handover; join the two files on
  time, not on these.
- Neighbour rows are rare. The cells are not time-aligned, so the UE reports
  the other cell only for a moment right after a handover.
- `/tmp/gnb.log` is buffered. On a running gNB the last reports may be
  missing, and a report cut off at the end of the file is skipped. Stop the
  gNB first (`q` in its console) if you need every report.
- The log is overwritten when the gNB starts. Copy it away before a restart.

## 9. Copy the results to your machine

```
scp kmubassh@<cn5g host>:/tmp/ngap.pcap .
scp kmubassh@<cudu host>:/tmp/meas.csv meas-gnb1.csv
scp kmubassh@<cudu2 host>:/tmp/meas.csv meas-gnb2.csv
```

`/tmp/ngap.pcap` is owned by the `tcpdump` user; it is readable, but remove it with `sudo rm`.

## Test run, 2026-10-08

Two forced handovers (gNB 1 -> 2 at 15:01:14 UTC, back at 15:01:23) with a
10 Hz ping:

| Check | Result |
|-------|--------|
| Ping | 263 of 263 answered |
| NGAP capture | 18 handover-related messages, the nine above once per handover |
| MRs on cudu | 511 reports in the log, 510 extracted (the last one was cut off by buffering), 9 neighbour rows |
| MRs on cudu2 | 60 reports in the log, 60 extracted, 6 neighbour rows |
