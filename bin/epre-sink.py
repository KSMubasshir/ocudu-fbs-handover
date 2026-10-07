#!/usr/bin/env python3
"""Live plotter/recorder for the upstream OCUDU EPRE PHY-TAP.

The upstream `tap_ul_resource_grid_epre_zmq` sends one message per UL slot
consisting of `nof_subc` float32 values (energy per subcarrier, summed over all
Rx ports and OFDM symbols). The wire format is a bare float32 blob — no header.
On a deployed cudu node the tap source is at
/var/tmp/ocudu/plugins/phy_tap_plugin_example/lib/external_processors/tap_ul_resource_grid_epre_zmq.cpp
(upstream plugin plus the patch in etc/phy_tap/).

The gNB side is enabled with (see etc/ocudu/gnb_rf_x310_ho_phytap.yml):
    expert_phy:
      allow_request_on_empty_uplink_slot: true   # also report UL slots with nothing scheduled
      enable_phy_tap: true
      phy_tap_arguments: tap_ul_epre=tcp://*:5555,enable_quiet_processing=true,log_level=info

Run from the repository root with uv (dependencies come from pyproject.toml):
    uv run bin/epre-sink.py --endpoint tcp://127.0.0.1:5555 [--record F]
    uv run bin/epre-sink.py --replay F --plot --scs-khz 30

Limitation: OCUDU creates the PHY tap factory once per DU, not per cell, so in a
multi-cell config every cell's UL slots arrive interleaved on the same port with
no per-message cell tag.

This tool subscribes ZMQ PULL to that endpoint and either:
  --plot     : shows a rolling EPRE-vs-frequency waterfall (dB) for the most
               recent `--history` slots.
  --record P : appends each raw float32 blob to file P (length-prefixed with
               a uint32 sample count so decoding is unambiguous).
  --replay P : plays back a recorded file at real-time-scaled pace.
"""

from __future__ import annotations

import argparse
import struct
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
import zmq


REC_HDR = struct.Struct("<I")  # per-record header: uint32 nof_subc


_warned_srsh = False


def decode_zmq_msg(msg: bytes) -> "np.ndarray | None":
    global _warned_srsh
    if msg[:4] == b"SRSH":
        # Wire magic of the SRS channel-estimate tap — wrong endpoint.
        if not _warned_srsh:
            _warned_srsh = True
            print(
                "[sink] receiving SRS channel-estimate (SRSH) messages, not EPRE blobs — "
                "you are connected to the tap_ul_srs_ce port. Use srs_ce_sink.py for this "
                "endpoint, or point --endpoint at the tap_ul_epre bind address.",
                file=sys.stderr,
            )
        return None
    if len(msg) == 0 or len(msg) % 4 != 0:
        return None
    return np.frombuffer(msg, dtype=np.float32)


def open_recorder(path: "Path | None"):
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("ab")
    print(f"[sink] recording raw EPRE blobs to {path}", file=sys.stderr)
    return f


def offline_iter(path: Path):
    with path.open("rb") as f:
        while True:
            hdr = f.read(REC_HDR.size)
            if not hdr:
                return
            if len(hdr) < REC_HDR.size:
                raise EOFError("truncated record header")
            (nof_subc,) = REC_HDR.unpack(hdr)
            payload = f.read(nof_subc * 4)
            if len(payload) < nof_subc * 4:
                raise EOFError("truncated payload")
            yield np.frombuffer(payload, dtype=np.float32)


class LivePlot:
    """Rolling waterfall of EPRE (dB) vs subcarrier index over history slots."""

    def __init__(self, history: int, fps: float, scs_khz: float,
                 vmin_db: float = -70.0, vmax_db: float = -20.0):
        import matplotlib.pyplot as plt
        from mpl_toolkits.axes_grid1 import make_axes_locatable

        self._plt = plt
        self._history = history
        self._render_period = 1.0 / max(fps, 0.1)
        self._last_render = 0.0
        self._dirty = False
        self._scs_khz = scs_khz
        self._vmin_db = vmin_db
        self._vmax_db = vmax_db
        self._n_subc: int = 0
        self._stack: "deque[np.ndarray]" = deque(maxlen=history)

        self._fig, self._ax = plt.subplots(1, 1, figsize=(11, 6))
        self._cax = make_axes_locatable(self._ax).append_axes(
            "right", size="1.8%", pad=0.08)
        self._cbar = None
        manager = getattr(self._fig.canvas, "manager", None)
        if manager is not None:
            manager.set_window_title("OCUDU UL resource-grid EPRE")
        plt.ion()
        plt.show(block=False)

    def push(self, epre_lin: np.ndarray) -> None:
        if self._n_subc == 0:
            self._n_subc = epre_lin.size
        elif epre_lin.size != self._n_subc:
            # Subcarrier count changed (e.g. gNB reconfigured) — restart the history.
            self._stack.clear()
            self._n_subc = epre_lin.size
        self._stack.append(10.0 * np.log10(np.maximum(epre_lin, 1e-20)))
        self._dirty = True

    def render_if_due(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and (not self._dirty or now - self._last_render < self._render_period):
            return
        self._last_render = now
        self._dirty = False
        if not self._stack:
            return

        stack = np.vstack(list(self._stack))
        freq_mhz = np.arange(self._n_subc) * self._scs_khz / 1000.0

        # Fixed color limits so levels are comparable across renders and runs.
        vmin = self._vmin_db
        vmax = self._vmax_db

        self._ax.clear()
        im = self._ax.imshow(
            stack,
            aspect="auto",
            interpolation="nearest",
            origin="lower",
            extent=(freq_mhz[0], freq_mhz[-1], 0, stack.shape[0]),
            vmin=vmin,
            vmax=vmax,
        )
        if self._cbar is None:
            self._cbar = self._fig.colorbar(im, cax=self._cax)
            self._cbar.set_label("EPRE (dB)", fontsize=9)
        else:
            self._cbar.update_normal(im)
        self._ax.set_title(
            f"UL EPRE waterfall  nof_subc={self._n_subc}  Δf={self._scs_khz:.0f} kHz  "
            f"({stack.shape[0]}/{self._history} slots history)"
        )
        self._ax.set_xlabel("frequency offset from grid start (MHz)")
        self._ax.set_ylabel("slot (recent = top)")

        self._fig.tight_layout()
        self._fig.canvas.draw_idle()
        self._plt.pause(0.001)


def run_live(
    endpoint: str,
    record_to: "Path | None",
    plot: bool,
    history: int,
    fps: float,
    scs_khz: float,
    recv_hwm: int,
    vmin_db: float,
    vmax_db: float,
) -> None:
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.PULL)
    sock.setsockopt(zmq.RCVHWM, recv_hwm)
    sock.setsockopt(zmq.LINGER, 0)
    sock.connect(endpoint)
    print(f"[sink] listening on {endpoint} (recv HWM={recv_hwm})", file=sys.stderr)

    recorder = open_recorder(record_to)
    plotter = LivePlot(history=history, fps=fps, scs_khz=scs_khz,
                       vmin_db=vmin_db, vmax_db=vmax_db) if plot else None

    poll_ms = max(1, int(1000.0 / max(fps, 1.0)))
    total = 0
    since_last_stat = 0
    empty_msgs = 0
    last_stat = time.monotonic()

    try:
        while True:
            drained_any = False
            while True:
                events = sock.poll(timeout=0 if drained_any else poll_ms, flags=zmq.POLLIN)
                if not events:
                    break
                msg = sock.recv(flags=zmq.NOBLOCK)
                drained_any = True
                total += 1
                since_last_stat += 1

                epre = decode_zmq_msg(msg)
                if epre is None:
                    if len(msg) == 0:
                        # Empty EPRE blobs: emitted by tap builds that predate the
                        # quiet-slot dimension fix. Counted, not printed per message.
                        empty_msgs += 1
                    else:
                        print(f"[sink] dropped malformed message len={len(msg)}", file=sys.stderr)
                    continue

                if recorder is not None:
                    recorder.write(REC_HDR.pack(epre.size))
                    recorder.write(msg)

                if plotter is None:
                    peak_lin = float(np.max(epre))
                    mean_lin = float(np.mean(epre))
                    print(
                        f"[sink] nof_subc={epre.size} "
                        f"peak={10*np.log10(max(peak_lin,1e-20)):+6.1f} dB "
                        f"mean={10*np.log10(max(mean_lin,1e-20)):+6.1f} dB"
                    )
                else:
                    plotter.push(epre)

            if recorder is not None and drained_any:
                recorder.flush()
            if plotter is not None:
                plotter.render_if_due()

            now = time.monotonic()
            if now - last_stat >= 5.0:
                rate = since_last_stat / (now - last_stat)
                extra = f", {empty_msgs} empty (pre-fix tap build?)" if empty_msgs else ""
                print(f"[sink] recv rate {rate:6.1f} msg/s (total {total}{extra})", file=sys.stderr)
                since_last_stat = 0
                empty_msgs = 0
                last_stat = now
    except KeyboardInterrupt:
        print("\n[sink] interrupted, shutting down", file=sys.stderr)
    finally:
        if recorder is not None:
            recorder.close()
        sock.close(0)
        ctx.term()


def replay(
    path: Path,
    plot: bool,
    history: int,
    fps: float,
    scs_khz: float,
    speed: float,
    vmin_db: float,
    vmax_db: float,
) -> None:
    """Playback a recorded EPRE binary log.

    speed > 0 paces roughly at 1 slot / ms scaled by speed. speed == 0 means
    no pacing (render is still throttled by --fps).
    """
    plotter = LivePlot(history=history, fps=fps, scs_khz=scs_khz,
                       vmin_db=vmin_db, vmax_db=vmax_db) if plot else None
    print(f"[sink] replaying {path}  speed={speed}× fps={fps}", file=sys.stderr)

    slot_period_s = 1e-3 / speed if speed > 0 else 0.0
    next_emit = time.monotonic()
    shown = 0

    for epre in offline_iter(path):
        if plotter is not None:
            if slot_period_s > 0:
                while True:
                    delay = next_emit - time.monotonic()
                    if delay <= 0:
                        break
                    plotter.render_if_due()
                    plotter._plt.pause(min(delay, 0.05))
                next_emit += slot_period_s
            plotter.push(epre)
            plotter.render_if_due()
        else:
            peak_lin = float(np.max(epre))
            print(
                f"nof_subc={epre.size} "
                f"peak={10*np.log10(max(peak_lin,1e-20)):+6.1f} dB"
            )
            if slot_period_s > 0:
                sleep = next_emit - time.monotonic()
                if sleep > 0:
                    time.sleep(sleep)
                next_emit += slot_period_s
        shown += 1

    print(f"[sink] end of file — {shown} records shown", file=sys.stderr)
    if plotter is not None:
        plotter.render_if_due(force=True)
        plotter._plt.ioff()
        plotter._plt.show()


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "EPRE sink").splitlines()[0])
    p.add_argument("--endpoint", default="tcp://127.0.0.1:5555",
                   help="ZMQ endpoint to PULL from (default: tcp://127.0.0.1:5555)")
    p.add_argument("--record", type=Path, default=None,
                   help="Path to append length-prefixed EPRE blobs to")
    p.add_argument("--replay", type=Path, default=None,
                   help="Playback a recorded binary log instead of listening")
    p.add_argument("--plot", action="store_true",
                   help="Show live/replayed EPRE waterfall (matplotlib)")
    p.add_argument("--history", type=int, default=512,
                   help="Number of slots to keep in the waterfall history (default: 512)")
    p.add_argument("--fps", type=float, default=10.0,
                   help="Max plot redraw rate (default: 10)")
    p.add_argument("--scs-khz", type=float, default=15.0,
                   help="Subcarrier spacing in kHz for the frequency axis (default: 15)")
    p.add_argument("--recv-hwm", type=int, default=10000,
                   help="ZMQ receive high-water mark (default: 10000)")
    p.add_argument("--vmin", type=float, default=-70.0,
                   help="Waterfall color-scale minimum in dB (default: -70)")
    p.add_argument("--vmax", type=float, default=-20.0,
                   help="Waterfall color-scale maximum in dB (default: -20)")
    p.add_argument("--speed", type=float, default=1.0,
                   help="Replay speed multiplier (default: 1.0, 0 = as fast as possible)")
    args = p.parse_args()

    if args.replay is not None:
        replay(args.replay, args.plot, args.history, args.fps, args.scs_khz, args.speed,
               args.vmin, args.vmax)
        return 0

    run_live(args.endpoint, args.record, args.plot, args.history, args.fps,
             args.scs_khz, args.recv_hwm, args.vmin, args.vmax)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
