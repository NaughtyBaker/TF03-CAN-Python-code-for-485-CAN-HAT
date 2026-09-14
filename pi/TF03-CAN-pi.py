#!/usr/bin/env python3
import argparse
import sys
import time

import can


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Read Benewake TF03-CAN distance/strength over SocketCAN."
    )
    p.add_argument("--channel", default="can0", help="SocketCAN interface (default: can0)")
    p.add_argument("--bitrate", type=int, default=1000000,
                   help="Bus bitrate in bit/s, used only in the bring-up hint (default: 1000000)")
    p.add_argument("--id", type=lambda v: int(v, 0), default=0x3,
                   help="CAN arbitration ID to accept (default: 0x3)")
    p.add_argument("--raw", action="store_true", help="Append the raw payload bytes")
    p.add_argument("--rate", action="store_true",
                   help="Print received frames per second to stderr")
    return p.parse_args(argv)


def hex_bytes(data):
    return " ".join(f"{byte:02X}" for byte in data)


def run(args):
    try:
        bus = can.interface.Bus(channel=args.channel, interface="socketcan")
    except can.CanError as exc:
        print(f"[ERROR] Cannot open {args.channel}: {exc}", file=sys.stderr)
        print(
            f"[INFO] Bring it up first: "
            f"sudo ip link set {args.channel} up type can bitrate {args.bitrate}",
            file=sys.stderr,
        )
        return 1

    if args.rate:
        print(
            f"[INFO] channel={args.channel} id={hex(args.id)} bitrate={args.bitrate}",
            file=sys.stderr,
        )

    count = 0
    window_start = time.monotonic()

    try:
        while True:
            msg = bus.recv(1.0)

            if args.rate and time.monotonic() - window_start >= 1.0:
                elapsed = time.monotonic() - window_start
                print(f"[rate] {count / elapsed:.1f} frames/s", file=sys.stderr)
                count = 0
                window_start = time.monotonic()

            if msg is None:
                continue
            if msg.arbitration_id != args.id:
                continue
            if len(msg.data) < 4:
                continue

            count += 1
            distance = msg.data[0] | (msg.data[1] << 8)
            strength = msg.data[2] | (msg.data[3] << 8)

            line = f"t={msg.timestamp:.3f} dist={distance}cm strength={strength}"
            if args.raw:
                line += f" raw={hex_bytes(msg.data)}"
            print(line, flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        bus.shutdown()

    return 0


def main():
    return run(parse_args())


if __name__ == "__main__":
    sys.exit(main())
