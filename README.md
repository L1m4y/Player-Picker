<p align="center">
  <img src="icons/title.png" width="520" alt="Player Picker">
</p>

<p align="center">Reassign physical gamepads to fixed virtual Xbox 360 controller slots.</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PyQt6-6.7+-41CD52?style=flat-square&logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/evdev-Linux-FC6D26?style=flat-square&logo=linux&logoColor=white" alt="evdev">
  <img src="https://img.shields.io/badge/Platform-Linux%20%2F%20Wayland-FCC624?style=flat-square&logo=linux&logoColor=black" alt="Platform">
  <img src="https://img.shields.io/badge/License-GPLv3-000000?style=flat-square" alt="License">
</p>

## Overview

| Interface | Slots | Compatibility | Communication |
| --- | --- | --- | --- |
| Qt6 | 4 | Xbox 360 emulation | Unix socket |

Player Picker routes physical gamepad events to one of four virtual Xbox 360 controllers, allowing reordering while a game, Steam or an emulator is already running.

## Features

- Real-time controller priority changes
- Virtual Xbox 360 controller emulation
- Qt6 interface for Plasma and Wayland
- Background daemon for input routing
- Hardware-safe event forwarding
- Configurable controller slot count
- Tray integration

## Requirements

- Linux
- Python 3.11 or newer
- `evdev`
- `PyQt6`
- `qt6-wayland` and `qt6-svg` on KDE or Wayland systems

## Installation

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
| Daemon access error | Add the user to the `input` group or run it as a privileged service |
| No controllers appear | Verify that `evdev` can open `/dev/input/event*` |
| Missing icons | Set `PLAYER_PICKER_ICONS` to the `icons` directory |
| Interface cannot connect | Verify the daemon socket with Python |

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
