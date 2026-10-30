![Player Picker](icons/title.png)

# Player Picker

Player Picker maps physical gamepads to fixed virtual Xbox 360 controller slots, allowing controller order changes without restarting games, Steam or emulators.

Virtual controllers are numbered one to four. Select a connected physical controller, then select the target slot to move it.

## Features

- Real-time controller priority changes
- Virtual Xbox 360 controller emulation
- PyQt6 interface for Plasma and Wayland
- Background daemon for input routing
- Four controller slots

## Dependencies

### Arch Linux

```bash
sudo pacman -S python-evdev python-pyqt6
```

### Python dependencies

```bash
pip install -r requirements.txt
```

## Running

Start the daemon:

```bash
sudo playerpicker-daemon
```

Start the interface:

```bash
playerpicker
```

`PLAYER_PICKER_SOCKET` can change the daemon socket path and `PLAYER_PICKER_ICONS` can change the icon directory.

## Service

Install and enable the included systemd unit:

```bash
sudo install -m 755 playerpicker.service /etc/systemd/system/playerpicker.service
sudo systemctl daemon-reload
sudo systemctl enable --now playerpicker
```

## Notes

- The daemon needs permission to read gamepad devices. Add your user to the `input` group or run it as a privileged service.
- Four virtual controllers are created at startup.
