# LTE FBS testbed bring-up (branch oai-lte-fbs)

Status of the 4G/LTE port of the FBS testbed, from the first live run on POWDER
(2026-10-15/16). The intent is to run the LTE twins of the 5G experiments:
benign handover (new), FBS idle reselection (`run-fbs-lte-exp`), FBS connected
mode (`run-fbs-lte-connected-exp`).

## Where it got to

The stack works layer by layer on the hardware. On an isolated home-eNB attach
test the **entire NAS attach completes on the network side** (S1AP capture on the
home EPC):

```
InitialUEMessage / Attach request / PDN connectivity request
Authentication request / response
Security mode command / complete
ESM information request / response
InitialContextSetupRequest / Attach accept / Activate default EPS bearer
UEContextReleaseComplete
```

So radio (band 1 FDD), S1 setup, LTE authentication, security and the EPC data
plane are all good: the MME sends the Attach Accept with the default bearer.

**Not yet working:** the UE does not finish registering (CEREG stays 0,0). Two
things seen around the final step:
- `NAS MAC verification failed` + `GUTI has already been allocated` on the MME:
  the UE attaches with a stale cached NAS security context / GUTI (from earlier
  failed attempts and the prior 5G registration on the same SIM). The MME
  re-authenticates and still reaches Attach Accept, but the context is released
  (`UEContextReleaseComplete`) and the UE never sends Attach Complete.
- The eNB releasing the UE on `ue_release_timer_rrc` timeout in earlier runs,
  i.e. the final RRC reconfiguration / Attach Complete step not closing.

Behaviour is flaky run to run (sometimes the UE does not camp at all). One cause
of that flakiness was **two lte-softmodem instances** left running on enb1 by
manual restarts -- always confirm a single instance (`pgrep -xc lte-softmodem`
= 1) before testing.

## Fixes already made and committed (the chain)

1. Band 40 TDD crashed OAI (`illegal subframe 6 for tdd_config 3`) -> **band 1
   FDD** (DL 2140 / UL 1950 MHz). Decided on the testbed.
2. eNB logs no S1-setup-success string -> `wait_enb` now keys on `got sync` +
   an ESTABLISHED SCTP assoc to the MME (36412).
3. USRP device-claim race on restart -> post-kill delay in `start_enb`.
4. eNB RX gain lowered (125->100) to cut PRACH false alarms in the conducted path.
5. Shared-SIM **SQN desync** (5G use advanced the USIM) -> Open5GS auto-resynced
   the HSS; auth now succeeds.
6. **UPF GTP-U vs SGW-U address collision**: in 4G both bind UDP 2152; the UPF
   must not sit on the SGW-U's LAN IP. `deploy-open5gs-epc.sh` now puts the UPF
   GTP-U on loopback. This was what made every attach fail at CreateSession.

## Resume here (prioritised)

1. Start exactly one eNB cleanly (kill all lte-softmodem first; verify count=1).
   Use the isolated home-only attach test (home eNB, FBS shielded) to iterate.
2. Give the UE a clean IMSI attach without the stale GUTI: detach + clear the
   cached EPS context, but **avoid** `AT+CFUN=1,1` mid-test (it regressed to
   not-camping here); prefer `AT+CGATT=0/1` and a plain airplane cycle, and
   restart the MME to drop its stale UE context first.
3. If Attach Accept is sent but the UE never sends Attach Complete, focus on the
   final RRC reconfiguration for the default DRB: watch the eNB RRC log for
   RRCConnectionReconfiguration / Complete, and consider raising the OAI eNB UE
   release timer and/or dropping to 25 PRB (5 MHz) to stabilise the radio.
4. Once a single UE attaches and holds, run `run-fbs-lte-exp` (idle lure) and
   `run-fbs-lte-connected-exp`, then build the benign-handover config (both eNBs
   on EPC 1 + X2) and its script.

Known-good capture method: S1AP on an EPC with `bin/s1ap-capture`, decode with
`tshark -r <pcap> -Y s1ap`; MME NAS flow via `journalctl -u open5gs-mmed`.

## Update (second live session): attach still not stable; what helped and hurt

Tried to drive a clean attach to unblock the three experiments. Findings:
- **50 PRB (10 MHz) got furthest**: in an isolated home-only test the full NAS
  attach completed to Attach Accept + default bearer. **25 PRB (5 MHz) regressed**
  -- the UE did not camp / sent no S1AP at all. Reverted the configs to 50 PRB.
- **Do not over-manipulate the modem.** `AT+CFUN=1,1` (reset) and `AT+CGATT=0`
  before attach left the UE not attaching at all. The plain flow
  (set LTE mode, airplane cycle via module-airplane/module-on) reached furthest.
- **OAI lte-softmodem runs as 2 processes** (a normal fork), not a duplicate.
  Count real instances with `pgrep -xc lte-softmodem` (exact name), never
  `pgrep -cf` (that also counts the sudo/numactl wrappers). Earlier "duplicate
  instance" worries were a counting artifact.
- Net: attach is flaky run to run. Best-known-good is 50 PRB + the plain modem
  flow + MME restarted for a clean context; from there the open problem is the
  UE not finalising registration after Attach Accept (Attach Complete / final
  RRC reconfiguration). Treat it as systematic stabilisation, not one more tweak.

The three experiments (benign handover, FBS idle reselection, FBS connected) and
their trace/packet/measurement collection all remain blocked on this one stable
attach; nothing else about them is known-broken.
