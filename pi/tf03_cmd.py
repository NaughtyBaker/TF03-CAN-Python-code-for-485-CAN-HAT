#!/usr/bin/env python3
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import can

import tf03_commands as cmds


def find_response(frames, cmd_id):
    for i in range(len(frames)):
        first = frames[i]
        if len(first) < 6 or first[0] != cmds.HEADER:
            continue
        total = first[1]
        if not 4 <= total <= 8:
            continue
        buffer = bytearray()
        for j in range(i, len(frames)):
            buffer.extend(frames[j])
            if len(buffer) >= total:
                candidate = bytes(buffer[:total])
                if candidate[2] != cmd_id:
                    break
                if (sum(candidate[:-1]) & 0xFF) == candidate[-1]:
                    return candidate
                break
    return None


def send_and_wait(bus, frame, cmd_id, args):
    msg = can.Message(
        arbitration_id=args.can_id,
        is_extended_id=args.extended,
        data=frame,
    )
    bus.send(msg)
    frames = []
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        response = bus.recv(remaining)
        if response is None:
            break
        data = bytes(response.data)
        frames.append(data)
        candidate = find_response(frames, cmd_id)
        if candidate is not None:
            return candidate, False
        if args.command == "single" and len(data) >= 4:
            return data, True
    return None, False


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Send a command to a Benewake TF03-CAN and print the response."
    )
    p.add_argument("command", help="raw | version | reset | frame-rate | baud | can-tx-id | ...")
    p.add_argument("value", nargs="?", help="parameter, or hex bytes for 'raw'")
    p.add_argument("--channel", default="can0", help="SocketCAN interface (default: can0)")
    p.add_argument("--can-id", type=lambda v: int(v, 0), default=0x3,
                   help="CAN ID the TF03 listens on (default: 0x3)")
    p.add_argument("--extended", action="store_true", help="send extended frames")
    p.add_argument("--timeout", type=float, default=1.0, help="response timeout in seconds")
    p.add_argument("--yes", action="store_true", help="confirm a state-changing command")
    p.add_argument("--dry-run", action="store_true", help="print the frame without sending")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        cmd_id, frame = cmds.build(args)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    print(f"[cmd] {args.command} id=0x{cmd_id:02X} len={frame[1]} frame={cmds.hex_bytes(frame)}")

    if args.dry_run or (args.command not in cmds.READ_ONLY and not args.yes):
        reason = "dry-run" if args.dry_run else "state-changing, add --yes"
        print(f"[skip] not sent ({reason})", file=sys.stderr)
        return 0

    try:
        bus = can.interface.Bus(channel=args.channel, interface="socketcan")
    except can.CanError as exc:
        print(f"[ERROR] Cannot open {args.channel}: {exc}", file=sys.stderr)
        print(f"[INFO] Bring it up first: sudo ip link set {args.channel} up type can", file=sys.stderr)
        return 1

    try:
        data, is_data = send_and_wait(bus, frame, cmd_id, args)
    finally:
        bus.shutdown()

    if data is None:
        print(f"[RX] no response within {args.timeout}s", file=sys.stderr)
        return 1

    if is_data:
        print(f"[RX] frame={cmds.hex_bytes(data)} -> {cmds.describe_data(data)}")
    else:
        print(f"[RX] frame={cmds.hex_bytes(data)} -> {cmds.describe(data)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
