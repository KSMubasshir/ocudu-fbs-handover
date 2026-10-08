# Troubleshooting notes

Problems hit while bringing up the inter-gNB handover experiment (2026-10-07),
in the order they appeared. Each entry gives the symptom, the cause, and the
fix. Commands for the normal run are in [commands.md](commands.md).

The login shell on the nodes is csh. Commands with `\"` inside double quotes
fail with `Unmatched '''.`; wrap them as `sudo bash -c '...'` instead.

## Where to look first

| Question | Where | Command |
|----------|-------|---------|
| Did the gNB accept its own cell? | cudu / cudu2 | `grep -n "F1 Setup\|Invalid cell measurement" /tmp/gnb.log` |
| Is the gNB keeping up with the radio? | gNB console | `Late` / `Underflow` / `Overflow` lines should be absent or small |
| Did the UE reach the core, and was it rejected? | cn5g | `sudo journalctl -u open5gs-amfd --no-pager --output cat \| tail -n 40` |
| What cell does the modem see? | ue1 / ue2 | `sudo bash -c 'chat -t 5 -sv "" AT OK "AT+QENG=\"servingcell\"" OK < /dev/ttyUSB2 > /dev/ttyUSB2'` |
| Does the UE report a neighbour cell? | cudu | `grep -a -c "measResultNeighCells" /tmp/gnb.log` |
| Did a handover run, and how did it end? | cudu / cudu2 | `grep -a "NGAP.*Handover\|Could not find" /tmp/gnb.log` |
| Which attenuator paths exist? | cudu / cudu2 | `/local/repository/bin/atten -l` |

`/tmp/gnb.log` is buffered. On an idle gNB it can stop mid-line and only catch
up when there is more traffic or the process exits, so a missing line does not
mean the event did not happen.

## 1. gNB will not start: `Could not convert: --ssb_arfcn = <dl_ssb_arfcn>`

**Cause.** The `SSBARFCN` placeholder was replaced with the literal text
`<dl_ssb_arfcn>` instead of a number.

**Fix.** On cudu and cudu2. This rewrites the whole line, so it works from any
state:

```
sudo sed -i "s/ssb_arfcn: .*/ssb_arfcn: 632256/" /var/tmp/etc/ocudu/gnb*_inter_ho.yml
```

`632256` is the `dl_ssb_arfcn=` value the gNB printed for `dl_arfcn: 632628`,
band 78, 20 MHz, 30 kHz SCS. Re-read it from the `Cell pci=1, ...` startup line
if the carrier changes.

## 2. `quectel-CM` shows `PS: Detached` and `SIOCSIFFLAGS: Network is down`

**Not a fault.** The modem is in airplane mode after boot and `quectel-CM` is
waiting. Bring it up from a second session:

```
/local/repository/bin/module-on.sh
```

`MCC: 0, MNC: 0` means the modem sees no network. `MCC: 999, MNC: 99` with
`PS: Detached` means it sees the cell but registration is failing (see 5).

## 3. Thousands of `Late` / `Underflow` / `Overflow` per second on gNB 1

**Symptom.** A UE attaches briefly with high downlink BLER, then drops.

**Cause.** The gNB was not keeping up with the X310. The inter-gNB config
inherited `srate: 92.16` from the two-cell config although it runs one 20 MHz
cell.

**Fix applied on cudu.** Lower the sample rate; `lo_offset: 45` must go too,
since a 45 MHz offset does not fit in a 23.04 MHz sample rate:

```
sudo sed -i -e "s/srate: 92.16/srate: 23.04/" -e "/lo_offset: 45/d" /var/tmp/etc/ocudu/gnb1_rf_x310_inter_ho.yml
```

The repo config still has 92.16; this change lives only on the node.

Host tuning was already in place (MTU 9000, 25 MB socket buffers). The profile
does not run the CPU script at boot:

```
/local/repository/bin/tune-sdr-iface.sh
/local/repository/bin/tune-cpu.sh
sudo cpupower frequency-set -g performance
```

## 4. Both gNBs connected to the AMF, but no UE can attach

**Symptom.** The AMF log shows both gNBs accepted. No UE row ever appears.

**Cause.** Each gNB rejected its own cell at startup, so there was no cell on
air to attach to. In `/tmp/gnb.log`:

```
[CU-CP] [E] Measurement object for ssb_freq=632256 already exists, but has different ssb_scs, smtc1 and/or smtc2
[CU-CP-F1] [W] Rejecting F1 Setup Request. Cause: Could not update cell measurement config
[DU-MNG] [E] F1 Setup procedure failed ... "F1 Setup Failure"
```

Both cells use the same SSB frequency, so OCUDU requires the neighbour entry's
SSB timing to equal the served cell's. The neighbour was declared with
`ssb_period: 5`; the served cell ran the default 10 ms.

**Fix.** Set the cells themselves to a 5 ms SSB period, on cudu and cudu2. Run
it once only:

```
sudo sed -i -e 's/^  pci: \([0-9]*\)$/  pci: \1\n  ssb:\n    ssb_period: 5/' /var/tmp/etc/ocudu/gnb*_inter_ho.yml
```

```
grep -n -A4 "^  pci:" /var/tmp/etc/ocudu/gnb*_inter_ho.yml
```

Expect `pci:`, one `ssb:` with `ssb_period: 5`, then `prach:`. The repo configs
already carry this change.

Running the sed twice leaves two `ssb:` blocks. That happened on cudu; the gNB
still started, but remove the duplicate (check the line numbers with the grep
first):

```
sudo sed -i '75,76d' /var/tmp/etc/ocudu/gnb1_rf_x310_inter_ho.yml
```

Connecting to the AMF only proves the wired side. A gNB can be registered with
the core and still have no cell.

## 5. ue2 will not register: `Registration reject [62]`

**Symptom.** ue1 attaches, ue2 does not. `quectel-CM` on ue2 shows
`MCC: 999, MNC: 99, PS: Detached`. The AMF log repeats every 10 s:

```
Cannot find Requested NSSAI [1]
    S_NSSAI[SST:1 SD:0x2]
Registration reject [62]
```

**Cause.** The ue2 modem (IMSI ending 118) keeps a slice setting from an
earlier experiment and asks for SD 2. The network offers only SST 1 / SD 1.
The core is correct: both subscribers have SD 1 in the database.

| | ue1 (works) | ue2 (rejected) |
|---|---|---|
| `AT+C5GNSSAI?` | `4,"01.000001"` | `0,""` |
| Stored slice for PLMN 99999 | `01.000001` | `01.000002` |

**Status: open.** Fix to try on ue2:

```
sudo bash -c 'chat -t 3 -sv "" AT OK "AT+C5GNSSAI=4,\"01.000001\"" OK < /dev/ttyUSB2 > /dev/ttyUSB2'
```

```
/local/repository/bin/module-airplane.sh
```

```
/local/repository/bin/module-on.sh
```

Check what the modem holds afterwards:

```
sudo sh -c "chat -t 3 -sv '' AT OK 'AT+C5GNSSAIRDP=3' OK < /dev/ttyUSB2 > /dev/ttyUSB2"
```

If the AMF still logs `SD:0x2`, the modem is using its stored slice for this
network. The fallback is to make the network accept SD 2 for ue2: add it to
the AMF and NSSF configs, both gNB configs, and the ue2 subscriber entry, then
restart the core and both gNBs.

## 6. Inter-gNB handover never starts from the attenuators

**Symptom.** `handover-gnb ue1 gnb2` runs, ue1 stays on PCI 1 and its signal
drops to about -112 dBm, nothing appears on cudu2. Same in the other direction.

**What the logs show.**

- gNB 1 sends the correct measurement config: SSB frequency 632256, 5 ms
  window, event A3 linked to it.
- ue1's periodic reports list only the serving cell. `measResultNeighCells`
  never appears, and the modem's `AT+QENG="neighbourcell"` is empty, even with
  the other cell 30 dB stronger.
- No `HandoverRequired` in either gNB log or in the AMF log.

**Cause.** The two cells are not time-aligned, and the modem only measures a
same-carrier neighbour whose timing it already knows. Evidence: straight after
a forced handover (below) the UE reported its old cell as a neighbour once
with a real level, then lost it within half a second.

The radios cannot be aligned as cabled (checked 2026-10-08 with the UHD Python
API, gNBs stopped):

| | X310 (cudu) | N300 (cudu2) |
|---|---|---|
| External 10 MHz | locks | locks |
| External PPS | none (last-PPS time never advances) | none (`Failed to capture PPS`) |
| GPS | no GPSDO | `gps_locked = false` |

So `clock: external` gives a common frequency but not common frame timing.
`sync: external` on the X310 does no harm but aligns nothing.

**Ruled out.**

- Attenuator paths: `atten -l` matches the numbers in `bin/update-attens`.
- gNB 2 and its RF path: with gNB 1 at 95, a modem cycle makes ue1 attach
  directly to PCI 3 at -81 dBm (CQI 15, 0% BLER).
- `deriveSSB-IndexFromCell`: OCUDU hardcodes it to `true`, which tells the UE
  the neighbour shares the serving cell's timing. Patching it to `false` (first
  hunk of the patch in section 7) is correct for unaligned cells but did not
  make the modem find the neighbour.

**Workaround: force the handover from the gNB console.** Type into the console
of the gNB serving the UE:

```
ho <serving pci> <rnti> <target pci>
```

For example `ho 1 4606 3` on cudu or `ho 3 4601 1` on cudu2. The RNTI is the
second column of the metrics table and changes after every handover. The UE
gets the handover command, searches for the target cell from scratch and
connects. Measured: four handovers back and forth, about 150 ms each from
`HandoverRequired` to `HandoverNotify`, 605 of 605 pings answered.

Both cells must be on air at similar levels when you do this
(`ru1ue1 5`, `gnb2ue1 0` gives about -83 and -81 dBm):

- The target must be strong enough to be found.
- The serving cell must not be much weaker than the other one. With the
  serving cell 18 dB below the other, the link failed within seconds and the
  UE reconnected from scratch on the stronger cell (`rrcReestablishmentRequest`
  rejected, then a new `rrcSetup`). That is not a handover.

**Real fix.** PPS to both radios (ask POWDER). Not available today.

**Other things learned here.**

- 60 on the gNB 1 paths does not remove the cell: PCI 1 stays at about
  -112 dBm with 10 dB SINR even at 95, through leakage in the matrix. The UE
  therefore never loses gNB 1 on its own.
- `handover-gnb` runs its whole fade in under 6 seconds.

## 7. Second handover of the same UE fails: `Could not find DU for CGI`

**Symptom.** The first forced handover works. Handing the same UE back fails:
the source logs `HandoverPreparationFailure`, the target logs
`Could not find DU for CGI=6576` (or 6592) and `Sending HandoverFailure`, the
AMF logs `ErrorIndication`, and the UE is released and loses its session.

**Cause.** OCUDU bug at commit `050a2bb72e`. The target gNB does not store the
serving GUAMI for a UE that arrives by NG handover (it is only set on initial
context setup). The next `HandoverRequired` for that UE carries an empty PLMN
in the target cell ID, so the target cannot match it to its cell.

**Fix.** One added line in
`lib/ngap/procedures/ngap_handover_resource_allocation_procedure.cpp`:
`ue_ctxt.serving_guami = request.guami;`. It is the second hunk of
[etc/ocudu-patches/050a2bb72e-inter-gnb-handover.patch](../etc/ocudu-patches/050a2bb72e-inter-gnb-handover.patch).
On cudu and cudu2, with the gNB stopped:

```
git -C /var/tmp/ocudu apply /local/repository/etc/ocudu-patches/050a2bb72e-inter-gnb-handover.patch
```

```
make -C /var/tmp/ocudu/build -j 48 gnb
```

`bin/deploy-ocudu.sh` does not apply this patch; a fresh experiment needs the
two commands above.

## Restarting the core

Rarely the fix; none of the problems above needed it. If you do, stop the gNBs
first and start them again afterwards.

```
sudo systemctl restart 'open5gs-*'
```

## State of the nodes versus the repo

Changes made by hand on the nodes that a fresh experiment will not have.
`bin/start-inter-gnb` applies the first three on every start.

| Change | cudu | cudu2 | In repo |
|--------|------|-------|---------|
| `ssb_arfcn: 632256` | yes | yes | placeholder in config; set by `start-inter-gnb` |
| `ssb_period: 5` on the cell | yes | yes | yes |
| `srate: 23.04`, no `lo_offset` | yes | n/a | 92.16 in config; set by `start-inter-gnb` |
| `clock: external` | yes | yes | no; `start-inter-gnb -c external` |
| `sync: external` | yes | no (no PPS) | no |
| OCUDU patch (section 7), rebuilt `gnb` | yes | yes | patch file only, not applied at deploy |
