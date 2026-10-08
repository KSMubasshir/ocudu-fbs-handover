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
| Does the UE report a neighbour cell? | cudu | `grep -n "measResultNeighCells" /tmp/gnb.log \| tail` |
| Which attenuator paths exist? | cudu / cudu2 | `/local/repository/bin/atten -l` |

`/tmp/gnb.log` is buffered. On an idle gNB it can stop mid-line at startup and
only catch up when the process exits.

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

## 6. Inter-gNB handover never starts

**Symptom.** `handover-gnb ue1 gnb2` runs, ue1 stays on PCI 1 and its signal
drops (about -112 dBm), nothing appears on cudu2.

**What the logs show.**

- gNB 1 sends the correct measurement config: SSB frequency 632256, 5 ms
  window, event A3 with a 3 dB offset.
- ue1's periodic reports list only PCI 1. No neighbour is ever reported, and
  the modem's neighbour-cell query is empty.
- No handover messages in gNB 1's log or the AMF log.
- gNB 2 is running and streaming samples to the N300.

**Ruled out.**

- Attenuator paths: `atten -l` matches the numbers in `bin/update-attens`.
- gNB 2 and its RF path: ue1 attaches directly to PCI 3 with a clean link
  (CQI 15, 0% BLER) when gNB 1 is faded out:

```
/local/repository/bin/update-attens ru1ue1 95
/local/repository/bin/update-attens gnb2ue1 0
```

**Likely cause (not confirmed).** The X310 and N300 run on separate internal
clocks, so the two cells are offset in frequency and timing, and the UE cannot
find gNB 2 as a same-frequency neighbour.

**Status: open.** Test in progress: lock both radios to the external 10 MHz
reference so the cells are aligned in frequency. Handover not yet re-run.

Stop both gNBs, then on cudu and cudu2:

```
sudo sed -i -e "s/clock: internal/clock: external/" -e "s/sync: internal/sync: external/" /var/tmp/etc/ocudu/gnb*_inter_ho.yml
```

The N300 has no PPS on its external input. With `sync: external` gNB 2 fails
at startup:

```
[ERROR] [RPC] Failed to capture PPS.
Error: couldn't set sync source: ... Failed to capture PPS.
OCUDU ERROR: Unable to create radio session.
```

So on cudu2 keep the external clock but put the time source back to internal:

```
sudo sed -i "s/sync: external/sync: internal/" /var/tmp/etc/ocudu/gnb2_rf_n300_inter_ho.yml
```

```
grep -n "clock:\|sync:" /var/tmp/etc/ocudu/gnb*_inter_ho.yml
```

gNB 2 starts with `clock: external`, `sync: internal`. A clean start is not
proof the N300 locked to a 10 MHz signal; the neighbour report below is.

Start both gNBs, put ue1 back on gNB 1, then hand over:

```
/local/repository/bin/update-attens ru1ue1 0
/local/repository/bin/update-attens gnb2ue1 95
```

```
/local/repository/bin/handover-gnb ue1 gnb2
```

Success shows first as PCI 3 appearing in ue1's measurement reports on cudu:

```
grep -n "measResultNeighCells" /tmp/gnb.log | tail
```

To revert:

```
sudo sed -i -e "s/clock: external/clock: internal/" -e "s/sync: external/sync: internal/" /var/tmp/etc/ocudu/gnb*_inter_ho.yml
```

## Restarting the core

Rarely the fix; none of the problems above needed it. If you do, stop the gNBs
first and start them again afterwards.

```
sudo systemctl restart 'open5gs-*'
```

## State of the nodes versus the repo

Changes made by hand on the nodes that a fresh experiment will not have:

| Change | cudu | cudu2 | In repo config |
|--------|------|-------|----------------|
| `ssb_arfcn: 632256` | yes | yes | no (placeholder) |
| `ssb_period: 5` on the cell | yes (duplicated) | yes | yes |
| `srate: 23.04`, no `lo_offset` | yes | n/a | no |
| `clock: external` | yes (as instructed, not re-checked) | yes | no |
| `sync: external` | yes (as instructed, not re-checked) | no (no PPS) | no |
