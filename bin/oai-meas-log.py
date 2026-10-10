#!/usr/bin/env python3
"""Log the UE measurement reports of an OAI gNB as CSV.

OAI does not write measurement reports to its log. It keeps the last report
of every UE in nrRRC_stats.log, which it rewrites about once a second. This
samples that file and prints one row per reported cell: the serving cell,
plus each neighbour cell if the UE reported any. Run it on the gNB node while
the gNB is running; Ctrl-C to stop.

    bin/oai-meas-log.py -o /tmp/meas.csv
    bin/oai-meas-log.py --interval 0.2
"""
import argparse
import csv
import re
import sys
import time

STATS = "/var/tmp/oai/cmake_targets/ran_build/build/nrRRC_stats.log"
UE = re.compile(r"^UE \d+ CU UE ID (\d+) DU UE ID \d+ RNTI ([0-9a-f]+)")
SERVING = re.compile(r"servingCellId \d+ MeasResultNR for phyCellId (\d+)")
NEIGHBOUR = re.compile(r"neighboring cell for phyCellId (\d+)")
QUANTITY = {
    "rsrp": re.compile(r"RSRP (-?[\d.]+) dBm"),
    "rsrq": re.compile(r"RSRQ (-?[\d.]+) dB"),
    "sinr": re.compile(r"SINR (-?[\d.]+) dB"),
}


def rows(text):
    """Yield (ue id, rnti, role, pci, rsrp, rsrq, sinr) for every cell in the file."""
    ue = cell = None
    for line in text.splitlines():
        m = UE.match(line)
        if m:
            ue, cell = m.groups(), None
            continue
        m = SERVING.search(line)
        if m:
            cell = ("serving", m.group(1))
            continue
        m = NEIGHBOUR.search(line)
        if m:
            cell = ("neighbour", m.group(1))
            continue
        if ue and cell and "resultSSB:" in line:
            values = []
            for regex in QUANTITY.values():
                m = regex.search(line)
                values.append(m.group(1) if m else "")
            yield (*ue, *cell, *values)
            cell = None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stats", nargs="?", default=STATS, help="nrRRC_stats.log of the running gNB (default %(default)s)")
    parser.add_argument("-o", "--output", help="CSV file to write (default stdout)")
    parser.add_argument("--interval", type=float, default=0.5, help="seconds between samples (default %(default)s)")
    args = parser.parse_args()

    out = open(args.output, "w", newline="") if args.output else sys.stdout
    writer = csv.writer(out)
    writer.writerow(["time", "cu_ue_id", "rnti", "cell", "pci", "rsrp_dbm", "rsrq_db", "sinr_db"])
    try:
        while True:
            try:
                with open(args.stats) as f:
                    text = f.read()
            except OSError:
                text = ""
            now = "%.3f" % time.time()
            for row in rows(text):
                writer.writerow([now, *row])
            out.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
