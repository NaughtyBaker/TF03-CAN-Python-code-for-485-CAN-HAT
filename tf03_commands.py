HEADER = 0x5A

FIXED_COMMANDS = {
    "version": (0x01, b""),
    "reset": (0x02, b""),
    "trigger-mode": (0x07, b"\x00"),
    "output-on": (0x07, b"\x01"),
    "output-off": (0x07, b"\x00"),
    "single": (0x04, b""),
    "save": (0x11, b""),
    "restore": (0x10, b""),
    "term-on": (0x91, b"\x01"),
    "term-off": (0x91, b"\x00"),
    "frame-std": (0x5D, b"\x00"),
    "frame-ext": (0x5D, b"\x01"),
    "dronecan-on": (0x84, b"\x00"),
    "dronecan-off": (0x84, b"\x01"),
    "switch-ttl": (0x45, b"\x01"),
    "switch-can": (0x45, b"\x02"),
    "lowpower-on": (0x83, b"\x01"),
    "lowpower-off": (0x83, b"\x00"),
    "modbus-enable": (0x6F, b"\x00"),
}

PARAM_COMMANDS = {
    "frame-rate": (0x03, 2),
    "baud": (0x06, 4),
    "can-tx-id": (0x50, 4),
    "can-rx-id": (0x51, 4),
    "can-baud": (0x52, 4),
    "out-of-range": (0x4F, 2),
    "offset": (0x69, 2),
    "modbus-addr": (0x70, 1),
}

READ_ONLY = {"version"}


def make_frame(cmd_id, params=b""):
    frame = bytes([HEADER, 4 + len(params), cmd_id]) + bytes(params)
    return frame + bytes([sum(frame) & 0xFF])


def hex_bytes(data):
    return " ".join(f"{byte:02X}" for byte in data)


def parse_hex(text):
    compact = text.replace(" ", "").replace("0x", "")
    if len(compact) % 2:
        raise ValueError("hex string must have an even number of digits")
    return bytes.fromhex(compact)


def build(args):
    if args.command == "raw":
        if args.value is None:
            raise ValueError("raw requires hex bytes, e.g. '5A 04 01 5F'")
        frame = parse_hex(args.value)
        if len(frame) < 4 or frame[0] != HEADER:
            raise ValueError("raw frame must start with 5A and be at least 4 bytes")
        return frame[2], frame
    if args.command in PARAM_COMMANDS:
        if args.value is None:
            raise ValueError(f"{args.command} requires a value")
        cmd_id, width = PARAM_COMMANDS[args.command]
        number = int(args.value, 0)
        params = number.to_bytes(width, "little", signed=number < 0)
        return cmd_id, make_frame(cmd_id, params)
    if args.command in FIXED_COMMANDS:
        cmd_id, params = FIXED_COMMANDS[args.command]
        return cmd_id, make_frame(cmd_id, params)
    raise ValueError(f"unknown command '{args.command}'")


def describe(data):
    cmd_id = data[2]
    payload = data[3:-1]
    if cmd_id == 0x01 and len(payload) >= 3:
        va, vb, vc = payload[0], payload[1], payload[2]
        return f"firmware version {vc}.{vb}.{va}"
    if cmd_id == 0x4F and len(payload) >= 2:
        return f"out-of-range value {payload[0] | (payload[1] << 8)} cm"
    return "raw response " + hex_bytes(data)


def describe_data(data):
    distance = data[0] | (data[1] << 8)
    strength = data[2] | (data[3] << 8)
    return f"data distance={distance}cm strength={strength}"
