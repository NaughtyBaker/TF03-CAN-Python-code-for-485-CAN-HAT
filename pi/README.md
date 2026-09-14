# TF03-CAN + Waveshare RS485 CAN HAT on Raspberry Pi

Read Benewake TF03 distance/strength over CAN using a Waveshare RS485 CAN HAT
(MCP2515 over SPI) on a Raspberry Pi, streamed to the console over SSH.

Verified with: Raspberry Pi Zero 2 W + Raspberry Pi OS Lite 32-bit (Trixie),
plain Waveshare RS485 CAN HAT (MCP2515, 12 MHz crystal, DIP-switch 120R
terminator), Benewake TF03-UART/CAN (older revision, R2/R3 removed, CAN mode).

## Hardware

- Raspberry Pi Zero 2 W, 40-pin header soldered.
- Waveshare RS485 CAN HAT (plain, 3.3V, MCP2515, 12 MHz crystal, DIP terminator).
- Benewake TF03-UART/CAN. On the older revision, resistors R2/R3 must be removed
  from the PCBA for CAN (see the V1.4.8 manual, "Figure 9"). Newer revisions use
  a software-controlled built-in 120R terminator, disabled by default.
- Separate 5-24V bench supply for the TF03.
- USB-UART adapter kept aside to revert TF03 CAN -> UART if needed.

## 1. Image and packages

Flash Raspberry Pi OS Lite (32-bit) with Raspberry Pi Imager; preset hostname,
user/password, WiFi, and enable SSH. Then:

    sudo apt update
    sudo apt install -y can-utils python3-can

python-can is 4.x, which is why the reader uses `interface='socketcan'`.

## 2. SPI + MCP2515 overlay

Append to `/boot/firmware/config.txt`:

    dtparam=spi=on
    dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000

Traps seen in practice:

- On Bookworm/Trixie the live config is `/boot/firmware/config.txt`. A separate
  `/boot/config.txt` may exist and is **not** read; edits there do nothing
  (symptom: no can0, no `spi` lines in `dmesg`).
- The vendor tutorial writes `mcp2515can0`; the real overlay is `mcp2515-can0`.
- Append the lines at the end, outside any non-matching `[section]`.

Reboot, then verify:

    sudo reboot
    dmesg | grep -iE 'mcp|spi'   # expect: mcp251x spi0.0 can0: MCP2515 successfully initialized.
    ip link show can0

A healthy interface reports, via `ip -details link show can0`, `state ERROR-ACTIVE`,
`bitrate 1000000`, `clock 6000000` (the 12 MHz crystal, halved by the driver).

## 3. Wiring

| TF03 (7-pin Molex) | Signal    | To                             |
|--------------------|-----------|--------------------------------|
| pin 1              | VCC 5-24V | bench supply +                 |
| pin 7              | GND       | bench supply -, **and Pi GND** |
| pin 3 (green)      | CAN_H     | HAT **H**                      |
| pin 2 (white)      | CAN_L     | HAT **L**                      |

- Tie TF03 GND to Pi GND (one wire) for a shared transceiver reference.
- Waveshare HAT has both RS485 (A/B) and CAN (H/L) terminals: use the **CAN H/L**
  pair, not RS485.
- Set the HAT DIP-switch CAN 120R terminator **ON** (bench link: one terminator;
  the TF03 end is unterminated after R2/R3 removal).

**Symptom: `candump` shows nothing and counters stay at 0** (no `bus-errors`) =
no differential activity, usually H/L swapped, wrong terminal, missing ground, or
TF03 unpowered. A bitrate mismatch instead raises error frames.

## 4. Bring can0 up on boot (systemd oneshot)

    sudo cp pi/tf03-can.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now tf03-can.service
    systemctl status tf03-can.service

If `command -v ip` is not `/sbin/ip` on your image, edit `ExecStart` accordingly.
For a one-off session you can instead run:

    sudo ip link set can0 up type can bitrate 1000000

## 5. Run

Copy to the Pi, then:

    scp pi/TF03-CAN-pi.py user@rpizero2w.local:/home/user/tf03/
    sudo python3 ~/tf03/TF03-CAN-pi.py

Options:

    --channel can0        SocketCAN interface (default: can0)
    --bitrate 1000000     used in the bring-up hint only
    --id 0x3              accepted arbitration ID (default: 0x3)
    --raw                 append raw payload bytes
    --rate                print frames/s to stderr

Example output:

    t=1789390974.736 dist=17cm strength=241
    t=1789390974.746 dist=17cm strength=241

The reader filters `arbitration_id == 0x3`, requires `dlc >= 4`, and decodes
distance and strength as little-endian uint16 (cm and raw counts). It keeps the
bus up on timeout and shuts the bus down cleanly on Ctrl+C.

## Deviations from the vendor tutorial

The vendor `TF03-CAN.py` targets Buster-era software and needs these changes:

1. `bustype='socketcan_ctypes'` -> `interface='socketcan'` (ctypes backend removed
   in python-can 4.x).
2. `except KeyboardInterrupt():` -> `except KeyboardInterrupt:` (the parenthesised
   form raises `TypeError` on Ctrl+C).
3. On a receive timeout the original ran `sudo ifconfig can0 down`, taking the bus
   down and then crashing on `recv` (`Errno 100, Network is down`). Removed.
4. Bring-up uses a single `ip link set can0 up type can bitrate 1000000`; no
   `ifconfig` (not present on Lite images).
5. Overlay name `mcp2515can0` -> `mcp2515-can0`.
