# Player Picker

A tool to reassign controller positions on Arch Linux.

Player Picker creates four virtual Xbox 360 controllers, allowing you to map physical gamepads to specific slots (P1-P4) without restarting games or Steam.

## Features

- Swap controller priority in real-time.
- Virtual Xbox 360 pad emulation for maximum compatibility.
- Qt6 interface for KDE Plasma and Wayland.
- Background daemon to handle input routing.

## Dependencies

Install all required packages with this command:

```bash
sudo pacman -S python-evdev python-pyqt6 qt6-wayland qt6-svg
