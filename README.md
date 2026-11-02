<p align="center">
  <img src="icons/title.png" width="520" alt="Player Picker">
</p>

<p align="center">Reassign physical gamepads to fixed virtual Xbox 360 controller slots.</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-808080?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PyQt6-6.7+-808080?style=flat-square&logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/evdev-Linux-808080?style=flat-square&logo=linux&logoColor=white" alt="evdev">
  <img src="https://img.shields.io/badge/Platform-Linux%20%2F%20Wayland-808080?style=flat-square&logo=linux&logoColor=white" alt="Platform">
</p>

## Installation

```bash
pip install -r requirements.txt
pip install .
python3 joy_daemon.py
python3 joy_gui.py
```

## Dependencies

- Arch Linux
  ```bash
  sudo pacman -S python python-pyqt6 python-evdev qt6-wayland qt6-svg
  ```
- Debian / Ubuntu
  ```bash
  sudo apt install python3 python3-pyqt6 python3-evdev qt6-wayland qt6-svg
  ```
- Fedora
  ```bash
  sudo dnf install python3 python3-pyqt6 python3-evdev qt6-wayland qt6-svg
  ```
- openSUSE
  ```bash
  sudo zypper install python3 python311 PyQt6 python3-evdev qt6-wayland qt6-svg
  ```

## Usage

- Start daemon: `playerpicker-daemon`
- Start GUI: `playerpicker`

Environment:

| Variable | Default | Description |
| --- | --- | --- |
| `PLAYER_PICKER_SOCKET` | `/run/joy_slot.sock` | Daemon socket path |
| `PLAYER_PICKER_ICONS` | `./icons` | Icon directory |
| `PLAYER_PICKER_SLOTS` | `4` | Number of virtual controllers |

Service:

```bash
sudo install -m 644 playerpicker.service /etc/systemd/system/playerpicker.service
sudo systemctl daemon-reload
sudo systemctl enable --now playerpicker
```
