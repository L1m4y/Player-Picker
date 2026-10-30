#!/usr/bin/env python3
import evdev
from evdev import ecodes as e
import asyncio
import argparse
import json
import os
from pathlib import Path
import glob

SOCKET_PATH = os.environ.get("PLAYER_PICKER_SOCKET", "/run/joy_slot.sock")

VIRTUAL_CAPS = {
    e.EV_KEY: [e.BTN_A, e.BTN_B, e.BTN_X, e.BTN_Y, e.BTN_TL, e.BTN_TR, e.BTN_SELECT, e.BTN_START, e.BTN_MODE, e.BTN_THUMBL, e.BTN_THUMBR, e.BTN_DPAD_UP, e.BTN_DPAD_DOWN, e.BTN_DPAD_LEFT, e.BTN_DPAD_RIGHT],
    e.EV_ABS: [
        (e.ABS_X, evdev.AbsInfo(value=0, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)),
        (e.ABS_Y, evdev.AbsInfo(value=0, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)),
        (e.ABS_RX, evdev.AbsInfo(value=0, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)),
        (e.ABS_RY, evdev.AbsInfo(value=0, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)),
        (e.ABS_Z, evdev.AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
        (e.ABS_RZ, evdev.AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
        (e.ABS_HAT0X, evdev.AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        (e.ABS_HAT0Y, evdev.AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
    ]
}

class VirtualGamepadManager:
    def __init__(self):
        self.virtual_slots = []
        self.phys_devices = {}
        for i in range(1, 5):
            ui = evdev.UInput(VIRTUAL_CAPS, name=f"Virtual Gamepad Slot {i}", vendor=0x045e, product=0x028e, version=0x0110)
            self.virtual_slots.append(ui)

    def is_gamepad(self, device):
        if "Virtual Gamepad" in device.name:
            return False
        caps = device.capabilities()
        keys = caps.get(e.EV_KEY, [])
        if e.KEY_A in keys or e.KEY_ENTER in keys:
            return False
        return any(key in keys for key in (e.BTN_GAMEPAD, e.BTN_SOUTH, e.BTN_A))

    async def handle_device(self, device_path):
        device = None
        try:
            device = evdev.InputDevice(device_path)
            if not self.is_gamepad(device):
                return
            used_slots = {info["slot"] for info in self.phys_devices.values()}
            avail = [slot for slot in range(4) if slot not in used_slots]
            current_slot = avail[0] if avail else 0
            self.phys_devices[device_path] = {"device": device, "slot": current_slot, "name": device.name}
            device.grab()
            async for event in device.async_read_loop():
                slot = self.phys_devices[device_path]["slot"]
                if 0 <= slot < len(self.virtual_slots):
                    self.virtual_slots[slot].write(event.type, event.code, event.value)
                    if event.type == e.EV_SYN:
                        self.virtual_slots[slot].syn()
        except Exception:
            return
        finally:
            if device is not None:
                try:
                    device.ungrab()
                except Exception:
                    pass
            self.phys_devices.pop(device_path, None)

    async def scan_devices(self):
        handled = set()
        while True:
            current = set(glob.glob("/dev/input/event*"))
            for path in current - handled:
                if os.access(path, os.R_OK | os.W_OK):
                    handled.add(path)
                    asyncio.create_task(self.handle_device(path))
            handled = {p for p in handled if os.path.exists(p)}
            await asyncio.sleep(1)

    async def handle_ipc(self, reader, writer):
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=1)
            if not data:
                return
            req = json.loads(data.decode())
            action = req.get("action")
            response = {"status": "error"}
            if action == "get_state":
                devices = [{"path": path, "name": info["name"], "slot": info["slot"]} for path, info in self.phys_devices.items()]
                response = {"status": "ok", "devices": devices}
            elif action == "set_slot":
                path = req.get("path")
                new_slot = req.get("slot")
                if path in self.phys_devices and isinstance(new_slot, int) and 0 <= new_slot <= 3:
                    old_slot = self.phys_devices[path]["slot"]
                    for candidate, info in self.phys_devices.items():
                        if candidate != path and info["slot"] == new_slot:
                            info["slot"] = old_slot
                    self.phys_devices[path]["slot"] = new_slot
                    response = {"status": "ok"}
            writer.write(json.dumps(response).encode())
            await writer.drain()
        except (asyncio.TimeoutError, json.JSONDecodeError, OSError):
            return
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

async def main_async(socket_path):
    manager = VirtualGamepadManager()
    if os.path.exists(socket_path):
        os.remove(socket_path)
    server = await asyncio.start_unix_server(manager.handle_ipc, path=socket_path)
    os.chmod(socket_path, 0o666)
    await asyncio.gather(manager.scan_devices(), server.serve_forever())

def main():
    parser = argparse.ArgumentParser(description="Player Picker virtual gamepad daemon")
    parser.add_argument("--socket", default=SOCKET_PATH, help="Unix socket path")
    args = parser.parse_args()
    try:
        asyncio.run(main_async(args.socket))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()

