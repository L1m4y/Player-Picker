<p align="center">
  <img src="icons/title.png" width="520" alt="Player Picker">
</p>

<p align="center">Reassign physical gamepads to fixed virtual Xbox 360 controller slots.</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-808080?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PyQt6-6.7+-808080?style=flat-square&logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/Platform-Linux%20%2F%20Wayland-808080?style=flat-square&logo=linux&logoColor=white" alt="Platform">
  <img src="https://img.shields.io/badge/License-GPLv3-808080?style=flat-square&logo=gnu&logoColor=white" alt="License">
</p>

Player Picker emulates four virtual Xbox 360 controllers and re-routes physical gamepad events to the selected slot in real time, swapping the previous occupant back automatically.

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

Service:

```bash
sudo install -m 644 playerpicker.service /etc/systemd/system/playerpicker.service
sudo systemctl daemon-reload
sudo systemctl enable --now playerpicker
```
