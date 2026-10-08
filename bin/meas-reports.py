#!/usr/bin/env python3
"""Extract the UE measurement reports from an OCUDU gNB log as CSV.

The gNB writes every RRC measurementReport to its log as JSON when
log.rrc_level is debug (set in the configs in etc/ocudu). This prints one row
per reported cell: the serving cell, plus each neighbour cell if the UE
reported any.

    bin/meas-reports.py                      # reads /tmp/gnb.log
    bin/meas-reports.py /tmp/gnb.log -o meas.csv
    bin/meas-reports.py --jsonl              # the raw reports, one JSON per line

The log is buffered and is overwritten every time the gNB starts; the last
reports of a running gNB may not be in the file yet.
"""
import argparse
import csv
import json
import re
import sys

HEADER = re.compile(
    r"^(\S+) \[RRC\s*\] \[D\] ue=(\d+) c-rnti=(0x[0-9a-f]+): Containerized measurementReport: \[$"
)


def reports(lines):
    """Yield (time, ue, rnti, measResults) for every report in the log."""
    head, body = None, []
    for line in lines:
        line = line.rstrip("\n")
        if head is None:
            m = HEADER.match(line)
            if m:
                head, body = m.groups(), ["["]
            continue
        body.append(line)
        if line == "]":
            try:
                msg = json.loads("\n".join(body))[0]["UL-DCCH-Message"]["message"]["c1"]
                yield (*head, msg["measurementReport"]["criticalExtensions"]["measurementReport"]["measResults"])
            except (ValueError, KeyError, IndexError):
                pass  # truncated by log buffering
            head = None


def cell_row(kind, cell):
    res = cell.get("measResult", {}).get("cellResults", {}).get("resultsSSB-Cell", {})
    # Reported values are the 3GPP TS 38.133 integer ranges.
    rsrp = res["rsrp"] - 156 if "rsrp" in res else ""
    rsrq = res["rsrq"] / 2 - 43 if "rsrq" in res else ""
    sinr = res["sinr"] / 2 - 23 if "sinr" in res else ""
    return [kind, cell.get("physCellId", ""), rsrp, rsrq, sinr]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log", nargs="?", default="/tmp/gnb.log", help="gNB log file (default: /tmp/gnb.log)")
    parser.add_argument("-o", "--output", help="write to this file instead of stdout")
    parser.add_argument("--jsonl", action="store_true", help="write the raw reports as JSON lines instead of CSV")
    args = parser.parse_args()

    out = open(args.output, "w", newline="") if args.output else sys.stdout
    with open(args.log, errors="replace") as log:
        if args.jsonl:
            for time, ue, rnti, res in reports(log):
                out.write(json.dumps({"time": time, "ue": int(ue), "rnti": rnti, "measResults": res}) + "\n")
            return
        writer = csv.writer(out)
        writer.writerow(["time", "ue", "rnti", "meas_id", "cell", "pci", "rsrp_dbm", "rsrq_db", "sinr_db"])
        for time, ue, rnti, res in reports(log):
            prefix = [time, ue, rnti, res.get("measId", "")]
            for serving in res.get("measResultServingMOList", []):
                writer.writerow(prefix + cell_row("serving", serving.get("measResultServingCell", {})))
            for neigh in res.get("measResultNeighCells", {}).get("measResultListNR", []):
                writer.writerow(prefix + cell_row("neighbour", neigh))


if __name__ == "__main__":
    main()
