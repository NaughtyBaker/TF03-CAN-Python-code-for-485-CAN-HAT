# TF03 UART read/write

Read distance/strength and send configuration commands to a Benewake TF03 over
UART, using any USB-UART adapter (`pyserial`). Works on the laptop and on the Pi.

The command set/checksum live in the shared `tf03_commands.py` at the repo root,
also used by `pi/tf03_cmd.py`.

## Wiring

TF03 UART is LVTTL 3.3V, 115200 8N1 by default (data frame 9 bytes:
`0x59 0x59 | dist_L dist_H | strength_L strength_H | 0x00 0x00 | checksum`).

    TF03 TX  -> adapter RX
    TF03 RX  -> adapter TX
    TF03 GND -> adapter GND

Use a 3.3V TTL adapter (not RS232). Example device: `/dev/ttyACM0` or
`/dev/ttyUSB0`.

## Read

    nix shell nixpkgs#python3Packages.pyserial -c \
      python3 uart/tf03_uart.py read --port /dev/ttyACM0

    t=1789393704.736 dist=17cm strength=241
    t=1789393704.746 dist=17cm strength=241

Options: `--baud 115200`, `--timeout 1.0`, `--count N` (0 = until Ctrl+C).

## Send a command

    python3 uart/tf03_uart.py send version --port /dev/ttyACM0
    python3 uart/tf03_uart.py send raw "5A 04 01 5F" --port /dev/ttyACM0
    python3 uart/tf03_uart.py send switch-can --port /dev/ttyACM0 --yes

Same command names as `pi/tf03_cmd.py` (`version`, `reset`, `save`, `switch-ttl`,
`switch-can`, `frame-rate`, `baud`, `out-of-range`, ...). State-changing commands
need `--yes`; `--dry-run` always suppresses sending. On UART the reply is a full
frame (no 6-byte chunking as on CAN).

Reads use the reference-style "trust the stream" approach: 9-byte frames with a
`0x59 0x59` header, no checksum validation.

## Switching interface

The TF03 boots in the interface selected by the `Switch Communication Interface`
command; the change takes effect **after `save` and a restart**.

CAN -> UART (send from the Pi over CAN, `pi/tf03_cmd.py`):

    sudo python3 ~/tf03/tf03_cmd.py --yes switch-ttl
    sudo python3 ~/tf03/tf03_cmd.py --yes save
    sudo python3 ~/tf03/tf03_cmd.py --yes reset

UART -> CAN (send over UART):

    python3 uart/tf03_uart.py send switch-can --port /dev/ttyACM0 --yes
    python3 uart/tf03_uart.py send save       --port /dev/ttyACM0 --yes
    python3 uart/tf03_uart.py send reset      --port /dev/ttyACM0 --yes

Do not switch away from the only live interface without the other one wired and
ready.
