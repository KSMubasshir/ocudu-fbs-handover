#!/usr/bin/env python3
"""
Send an rrm_policy_ratio_set command to a running ocudu gNB.

The ocudu remote-control WebSocket must be enabled in the gNB YAML config
(remote_control.enabled: true). The deployed POWDER config
etc/ocudu/gnb_rf_x310_ho.yml enables it on 0.0.0.0:8001.

Usage (from the repository root):
    uv run bin/rrm-policy-set.py --min 50 --max 100
    uv run bin/rrm-policy-set.py --min 30 --max 70 --dedicated 20
    uv run bin/rrm-policy-set.py --min 50 --max 100 --host 192.168.1.2

Requirements:
    Run with uv; dependencies (websockets) are resolved from pyproject.toml.
"""

import argparse
import asyncio
import json
import sys

import websockets


def _check_ratio(name, value):
    if value is None:
        return
    if not 0 <= value <= 100:
        print(f"error: --{name} must be in [0, 100], got {value}", file=sys.stderr)
        sys.exit(1)


def build_payload(plmn, sst, sd, min_ratio, max_ratio, dedicated):
    policies = {
        "resourceType": "PRB",
        "rRMPolicyMemberList": [{"plmn": plmn, "sst": sst, "sd": sd}],
    }
    if min_ratio is not None:
        policies["min_prb_policy_ratio"] = min_ratio
    if max_ratio is not None:
        policies["max_prb_policy_ratio"] = max_ratio
    if dedicated is not None:
        policies["dedicated_ratio"] = dedicated
    return {"cmd": "rrm_policy_ratio_set", "policies": policies}


async def send(host, port, payload):
    uri = f"ws://{host}:{port}"
    print(f"Connecting to {uri}...", file=sys.stderr)
    async with websockets.connect(uri) as ws:
        print(f"Sending: {json.dumps(payload)}", file=sys.stderr)
        await ws.send(json.dumps(payload))
        response = await ws.recv()
        print(response)
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            return 1
        return 1 if "error" in parsed else 0


def main():
    parser = argparse.ArgumentParser(
        description="Send rrm_policy_ratio_set to a running ocudu gNB.",
    )
    parser.add_argument("--host", default="127.0.0.1",
                        help="WebSocket host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8001,
                        help="WebSocket port (default: 8001)")
    parser.add_argument("--plmn", default="99999",
                        help="PLMN (default: 99999)")
    parser.add_argument("--sst", type=int, default=1,
                        help="Slice Service Type (default: 1)")
    parser.add_argument("--sd", type=int, default=1,
                        help="Slice Differentiator (default: 1)")
    parser.add_argument("--min", type=int, dest="min_ratio",
                        help="Minimum PRB ratio [0-100]")
    parser.add_argument("--max", type=int, dest="max_ratio",
                        help="Maximum PRB ratio [0-100]")
    parser.add_argument("--dedicated", type=int,
                        help="Dedicated PRB ratio [0-100]")
    args = parser.parse_args()

    if args.min_ratio is None and args.max_ratio is None and args.dedicated is None:
        print("error: at least one of --min, --max, --dedicated is required",
              file=sys.stderr)
        sys.exit(1)

    _check_ratio("min", args.min_ratio)
    _check_ratio("max", args.max_ratio)
    _check_ratio("dedicated", args.dedicated)

    payload = build_payload(
        args.plmn, args.sst, args.sd,
        args.min_ratio, args.max_ratio, args.dedicated,
    )

    try:
        rc = asyncio.run(send(args.host, args.port, payload))
    except websockets.exceptions.WebSocketException as e:
        print(f"WebSocket error: {e}", file=sys.stderr)
        sys.exit(1)
    sys.exit(rc)


if __name__ == "__main__":
    main()
