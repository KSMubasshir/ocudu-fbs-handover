# Second gNB on its own core (foreign PLMN): experiment commands

Copy-paste sheet for the `oai-second-core` branch: gNB 1 on core 1 (`cn5g`,
PLMN 999/99) and gNB 2 on a separate core 2 (`cn5g2`, PLMN 001/01). The two
networks share nothing; there is no handover. The Quectel SIMs are homed on
999/99, so the UE registers on gNB 1 and only sees gNB 2's foreign cell.

Hostnames change on every POWDER instantiation; take them from the portal.
The login shell on the nodes is `tcsh`.

## Whole run from your machine

`bin/run-second-core-exp` does sections 1 to 8 over SSH and copies the
results to `traces/second-core-<date>-<time>/`. Add the new core to
`hosts.env` first:

```
CN5G2=<cn5g2 hostname>
```

```
bin/run-second-core-exp            # 30 s per phase, with scan and fade
bin/run-second-core-exp -d 60 -S   # 60 s per phase, no modem scan
```

Phases: ue1 attached on gNB 1 alone; both cells at similar levels (plus an
`AT+QSCAN` network scan); gNB 1 faded out with only the foreign cell left;
gNB 1 back. `timeline.txt` has the UTC time of every phase change. Fetched:
both cores' NGAP pcap, NGAP text and AMF/SMF/UPF log, both gNB logs and
sampled measurement reports, ue1's serving cell once a second, the ping and
the scan.

## SSH

```
# cn5g (core 1, 999/99)
ssh kmubassh@<cn5g>
```

```
# cn5g2 (core 2, 001/01)
ssh kmubassh@<cn5g2>
```

```
# cudu (gNB 1, X310 -> core 1)
ssh kmubassh@<cudu>
```

```
# cudu2 (gNB 2, N300 -> core 2)
ssh kmubassh@<cudu2>
```

```
# ue1
ssh kmubassh@<ue1>
```

Wait until every compute node shows "Finished" in the portal's Startup column.
OAI is built when `/var/tmp/oai-setup-complete` exists on `cudu`/`cudu2`;
each core is up when `/var/tmp/open5gs-setup-complete` exists.

## 1. Core logs (one session on each core)

```
# on cn5g AND on cn5g2
sudo journalctl -u open5gs-amfd -u open5gs-smfd -f --output cat
```

Confirm each core's PLMN:

```
# on cn5g2 — expect mcc 001 / mnc 01
grep -A1 plmn_support /etc/open5gs/amf.yaml
```

## 2. Start the gNBs

Same command on both; it picks gNB 1 -> core 1 on `cudu` and gNB 2 -> core 2
on `cudu2`. Output also goes to `/tmp/gnb.log`.

```
# on cudu AND on cudu2
/local/repository/bin/start-oai-gnb
```

gNB 1 should complete NG Setup in the `cn5g` AMF log; gNB 2 in the `cn5g2`
AMF log. gNB 2 reaching `cn5g` (or vice versa) would mean the AMF address in
its config is wrong.

## 3. Only gNB 1 reaches ue1 to start (cudu)

```
/local/repository/bin/update-attens ru1ue1 0
```

```
/local/repository/bin/update-attens gnb2ue1 95
```

## 4. Attach ue1 (it joins gNB 1 / core 1)

### Connection manager (ue1, session 1)

```
sudo quectel-CM -s internet -4
```

### Modem out of airplane mode (ue1, session 2)

```
/local/repository/bin/module-on.sh
```

### Confirm the serving cell and PLMN, and ping core 1's UPF

```
cd /local/repository && uv run bin/ue_metrics.py
```

```
ping 10.45.0.1
```

`ue_metrics.py` should show PCI 1, PLMN 999/99. The ping goes through core 1's
UPF.

## 5. Bring gNB 2's cell up at ue1 and show the UE does not move to it

### Raise gNB 2's level (cudu)

```
/local/repository/bin/update-attens gnb2ue1 0
```

### Scan from the modem (ue1)

```
cd /local/repository && uv run bin/quectel_control.py scan
```

The scan (`AT+QSCAN`) should list the foreign cell (PLMN 001/01, PCI 3)
alongside the home cell (999/99, PCI 1). The modem stays registered on gNB 1:
`ue_metrics.py` keeps reporting PCI 1 and the ping keeps flowing. Fading gNB 1
down does not move the UE onto 001/01 in SA; it drops instead.

```
# optional: fade toward gNB 2 and watch the UE lose service, not hand over
/local/repository/bin/handover-gnb ue1 gnb2
```

## 6. Observe gNB 2 standalone (optional)

gNB 2 and core 2 are a complete network for a SIM homed on 001/01. Its cell is
on air and its core logs are on `cn5g2`. With a 001/01 SIM the subscribers
provisioned on `cn5g2` (IMSI `001010000000141`, `...118`) would let a UE attach
there directly.

## 7. NGAP captures (optional, on each core)

```
# on cn5g OR cn5g2 — second session, runs until Ctrl-C
/local/repository/bin/ngap-capture /tmp/ngap.pcap
```

```
tshark -r /tmp/ngap.pcap -Y ngap
```

Each core only ever sees its own gNB's NGAP (NG Setup, registration); no
handover messages, since the cores are independent.

## 8. Stop

```
# ue1
/local/repository/bin/module-airplane.sh
```

```
# cudu AND cudu2 — Ctrl-C in the gNB session, or:
sudo pkill nr-softmodem
```

## Changing the foreign PLMN

Change it in two places and reinstantiate (or redeploy):

- `etc/oai/gnb2_n300_core2.conf`: `plmn_list = ({ mcc = ...; mnc = ...; ... })`
- `profile.py`: `FOREIGN_MCC` / `FOREIGN_MNC` (passed to `deploy-open5gs.sh`
  on `cn5g2`)

Give MCC as 3 digits and MNC as 2 digits (e.g. `001`/`01`) so the leading
zeros reach the Open5GS config, where the MNC length is taken from the digit
count.
