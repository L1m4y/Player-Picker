![Player Picker](icons/title.png)

# Player Picker

Player Picker maps physical gamepads to four virtual Xbox 360 controller slots. It allows reordering controllers while a game, Steam, or emulator is already running.

Virtual slots are numbered from one to four. Select a connected physical controller, then select the target slot to move it.

## Features

- Real-time controller priority changes
- Virtual Xbox 360 controller emulation
- Qt6 interface for Plasma and Wayland
- Background daemon for input routing
- Hardware-safe event forwarding
- Configurable slot count

## Requirements

- Linux
- Python 3.11 or newer
- `evdev`
- `PyQt6`
- `qt6-wayland` and `qt6-svg` on KDE or Wayland systems

## Installation

Install the Python dependencies:

```bash
pip install -r requirements.txt
pip install .
```

Or run directly from the repository:

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

Environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `PLAYER_PICKER_SOCKET` | `/run/joy_slot.sock` | Daemon socket path |
| `PLAYER_PICKER_ICONS` | `./icons` | Icon directory |
| `PLAYER_PICKER_SLOTS` | `4` | Number of virtual controllers |

## Service

Install and enable the included systemd unit:

```bash
sudo install -m 644 playerpicker.service /etc/systemd/system/playerpicker.service
sudo systemctl daemon-reload
sudo systemctl enable --now playerpicker
```

## Troubleshooting

- If the daemon reports access errors, add the user to the `input` group or run it as a privileged service.
- If no controllers appear, verify that `evdev` can open `/dev/input/event*`.
- If the interface starts without icons, set `PLAYER_PICKER_ICONS` to the `icons` directory.
- Test the daemon socket manually:

```bash
python3 -c "import json, socket; s=socket.socket(socket.AF_UNIX); s.connect('/run/joy_slot.sock'); s.sendall(b'{\"action\":\"get_state\"}'); print(s.recv(4096))"
```

## Architecture

The daemon creates virtual Xbox 360 controllers with `evdev`, grabs physical input devices and mirrors their events to the assigned slot. The Qt interface communicates with the daemon through a small Unix socket using JSON messages.

See `docs.md` for more detail.

## Project Structure

```text
joy_daemon.py      Daemon and virtual controller routing
joy_gui.py         PyQt6 interface
icons/             Interface assets
docs.md            Architecture notes
playerpicker.service systemd unit
pyproject.toml     Packaging metadata
```

## License

GNU General Public License v3.0. See `LICENSE`.
