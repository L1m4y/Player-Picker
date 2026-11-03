<p align="center">
  <img src="icons/title.png" width="520" alt="Player Picker">
</p>

<p align="center">Reassign physical gamepads to fixed virtual controller slots.</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-808080?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PyQt6-6.7+-808080?style=flat-square&logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/Platform-Linux%20%2F%20Wayland-808080?style=flat-square&logo=linux&logoColor=white" alt="Platform">
  <img src="https://img.shields.io/badge/License-GPLv3-808080?style=flat-square&logo=gnu&logoColor=white" alt="License">
</p>

It listens to physical controllers, forwards their events to virtual Xbox 360 slots and rearranges
the mapping instantly, so previous occupants swap back without stopping gameplay.

## Installation

Arch Linux:

```bash
cd packaging
makepkg -si
```

From source:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Manual service:

```bash
sudo install -m 644 playerpicker.service /etc/systemd/system/playerpicker.service
sudo systemctl daemon-reload
sudo systemctl enable --now playerpicker
```

Install system dependencies as appropriate for your distribution (`python-evdev`, `python-pyqt6`,
`qt6-wayland`, `qt6-svg`).

## Permissions

The daemon needs `/dev/uinput` and the `/dev/input/event*` nodes. Run it as root through the
service, or with `sudo` when running by hand. The GUI runs as the desktop user.

## Usage

Start `playerpicker-daemon`, then `playerpicker`. Click an occupied tile, then click another
tile to move the controller there. Click the selected tile again to cancel.

## Environment variables

| Variable | Default | Effect |
| --- | --- | --- |
| `PLAYER_PICKER_SOCKET` | `/run/joy_slot.sock` | Daemon socket path used by both binaries |
| `PLAYER_PICKER_SLOTS` | `4` | Virtual slot count, from `1` to `8` |
| `PLAYER_PICKER_ICONS` | unset | Directory overriding the bundled icons |

## Troubleshooting

- If the GUI says the daemon is waiting, start `playerpicker-daemon` or the service.
- Run with `--log-level DEBUG` to inspect device detection and IPC requests.
- Invalid `PLAYER_PICKER_SLOTS` values are rejected with a clear error instead of being clamped.

## Development

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
```

## License

GPLv3. See [LICENSE](LICENSE).
EOF
echo ok