<p align="center">
  <img src="icons/title.png" width="320" alt="Player Picker">
</p>

<p align="center">
  <a href="https://github.com/L1m4y/Player-Picker">Repository</a> ·
  <a href="https://github.com/L1m4y/Player-Picker/issues">Issues</a> ·
  <a href="https://github.com/L1m4y/Player-Picker/blob/main/LICENSE">License</a>
</p>

Reassign physical gamepads to fixed virtual Xbox 360 controller slots while games, Steam or emulators are already running.

Player Picker creates four virtual Xbox 360 controllers and routes physical gamepad events to the selected slot in real time.

## Overview

| Field | Details |
| --- | --- |
| Platform | Linux |
| Interface | Qt6 |
| Compatibility | Xbox 360 controller emulation |
| Slots | Four by default, configurable |
| Communication | Unix socket with JSON |

## Features

- Real-time controller priority changes
- Virtual Xbox 360 controller emulation
- Qt6 interface for Plasma and Wayland
- Background daemon for input routing
- Hardware-safe event forwarding
- Configurable controller slot count
- Tray integration

## Requirements

| Tool | Version |
| --- | --- |
| Python | 3.11 or newer |
| evdev | 1.8 or newer |
| PyQt6 | 6.7 or newer |
| qt6-wayland | Desktop integration |
| qt6-svg | Icon rendering |

## Installation

Install dependencies on Arch Linux:

```bash
sudo pacman -S python-evdev python-pyqt6 qt6-wayland qt6-svg
pip install -r requirements.txt
pip install .
```

Run directly from the repository:

```bash
python3 joy_daemon.py
python3 joy_gui.py
```

## Usage

Start the daemon:

```bash
playerpicker-daemon
```

Start the interface:

```bash
playerpicker
```

Configuration:

| Variable | Default | Description |
| --- | --- | --- |
| `PLAYER_PICKER_SOCKET` | `/run/joy_slot.sock` | Daemon socket path |
| `PLAYER_PICKER_ICONS` | `./icons` | Interface icon directory |
| `PLAYER_PICKER_SLOTS` | `4` | Number of virtual controllers |

## Service

```bash
sudo install -m 644 playerpicker.service /etc/systemd/system/playerpicker.service
sudo systemctl daemon-reload
sudo systemctl enable --now playerpicker
```

## Workflow

1. Start the daemon.
2. Open Player Picker.
3. Click a connected physical controller.
4. Click the target slot.
5. The controller moves instantly and the previous occupant swaps back to the source slot.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Daemon access error | Add the user to the `input` group or run as a privileged service |
| No controllers appear | Verify that `evdev` can open `/dev/input/event*` |
| Missing icons | Set `PLAYER_PICKER_ICONS` to the `icons` directory |
| Interface cannot connect | Verify the daemon socket with `socat` or Python |

## Architecture

The daemon creates virtual Xbox 360 controllers with `evdev`, grabs physical input devices and mirrors their events to the assigned slot. The PyQt6 interface communicates through a small Unix socket using JSON messages.

See `docs.md` for more detail.

## Project Structure

```text
joy_daemon.py
joy_gui.py
icons/
docs.md
playerpicker.service
pyproject.toml
requirements.txt
```

## License

GNU General Public License v3.0. See `LICENSE`.
