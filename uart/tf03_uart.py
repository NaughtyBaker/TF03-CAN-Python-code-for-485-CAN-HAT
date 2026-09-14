#!/usr/bin/env python3
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import serial

import tf03_commands as cmds

UART_HEADER = 0x59


def open_port(args):
    try:
        return serial.Serial(args.port, args.baud, timeout=args.timeout)
    except serial.SerialException as exc:
        print(f"[ERROR] Cannot open {args.port}: {exc}", file=sys.stderr)
        return None


def read_loop(ser, count):
    seen = 0
    while True:
        frame = ser.read(9)
        if len(frame) != 9:
            continue
        if frame[0] != UART_HEADER or frame[1] != UART_HEADER:
            continue
        distance = frame[2] | (frame[3] << 8)
        strength = frame[4] | (frame[5] << 8)
        print(f"t={time.time():.3f} dist={distance}cm strength={strength}", flush=True)
        seen += 1
        if count and seen >= count:
            return


def find_frame(buffer, cmd_id):
    i = 0
    while i < len(buffer):
        if buffer[i] != cmds.HEADER:
            i += 1
            continue
        if i + 2 > len(buffer):
            return None
        length = buffer[i + 1]
        if not 4 <= length <= 8:
            i += 1
            continue
        if i + length > len(buffer):
            return None
        candidate = bytes(buffer[i:i + length])
        if candidate[2] == cmd_id:
            return candidate
        i += 1
    return None


def read_reply(ser, cmd_id, timeout):
    deadline = time.monotonic() + timeout
    ser.timeout = 0.05
    buffer = bytearray()
    while time.monotonic() < deadline:
        chunk = ser.read(1)
        if chunk:
            buffer.extend(chunk)
            candidate = find_frame(buffer, cmd_id)
            if candidate is not None:
                return candidate
        if len(buffer) > 1024:
            del buffer[:512]
    return None


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Read from or send commands to a Benewake TF03 over UART."
    )
    sub = p.add_subparsers(dest="mode", required=True)

    r = sub.add_parser("read", help="print distance/strength data frames")
    r.add_argument("--port", required=True, help="serial device, e.g. /dev/ttyACM0")
    r.add_argument("--baud", type=int, default=115200)
    r.add_argument("--timeout", type=float, default=1.0)
    r.add_argument("--count", type=int, default=0, help="stop after N frames (0 = forever)")

    s = sub.add_parser("send", help="send a command and print the reply")
    s.add_argument("command", help="raw | version | reset | switch-can | frame-rate | ...")
    s.add_argument("value", nargs="?", help="parameter, or hex bytes for 'raw'")
    s.add_argument("--port", required=True, help="serial device, e.g. /dev/ttyACM0")
    s.add_argument("--baud", type=int, default=115200)
    s.add_argument("--timeout", type=float, default=1.0)
    s.add_argument("--yes", action="store_true", help="confirm a state-changing command")
    s.add_argument("--dry-run", action="store_true", help="print the frame without sending")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.mode == "read":
        ser = open_port(args)
        if ser is None:
            return 1
        try:
            read_loop(ser, args.count)
        except KeyboardInterrupt:
            pass
        finally:
            ser.close()
        return 0

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

    ser = open_port(args)
    if ser is None:
        return 1

    try:
        ser.reset_input_buffer()
        ser.write(frame)
        ser.flush()
        reply = read_reply(ser, cmd_id, args.timeout)
    finally:
        ser.close()

    if reply is None:
        print(f"[RX] no response within {args.timeout}s", file=sys.stderr)
        return 1

    print(f"[RX] frame={cmds.hex_bytes(reply)} -> {cmds.describe(reply)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
