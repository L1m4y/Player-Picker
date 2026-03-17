#!/usr/bin/env python3
import evdev
from evdev import ecodes as e
import asyncio
import os
import glob
import json

SOCKET_PATH = "/run/joy_slot.sock"

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
        if "Virtual Gamepad" in device.name: return False
        caps = device.capabilities()
        if e.EV_KEY in caps:
            keys = caps[e.EV_KEY]
            if e.BTN_GAMEPAD in keys or e.BTN_SOUTH in keys or e.BTN_A in keys:
                if e.KEY_A not in keys and e.KEY_ENTER not in keys: return True
        return False

    async def handle_device(self, device_path):
        try:
            device = evdev.InputDevice(device_path)
            if not self.is_gamepad(device): return
            
            used_slots = {info["slot"] for info in self.phys_devices.values()}
            avail = [i for i in range(4) if i not in used_slots]
            current_slot = avail[0] if avail else 0
            
            self.phys_devices[device_path] = {"device": device, "slot": current_slot, "name": device.name}
            device.grab()

            async for event in device.async_read_loop():
                slot = self.phys_devices[device_path]["slot"]
                self.virtual_slots[slot].write(event.type, event.code, event.value)
                if event.type == e.EV_SYN: self.virtual_slots[slot].syn()
        except Exception: pass
        finally:
            if device_path in self.phys_devices:
                try: self.phys_devices[device_path]["device"].ungrab()
                except: pass
                del self.phys_devices[device_path]

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
            data = await reader.read(1024)
            if not data: return
            req = json.loads(data.decode())
            action = req.get("action")
            res = {"status": "error"}

            if action == "get_state":
                devs = [{"path": p, "name": i["name"], "slot": i["slot"]} for p, i in self.phys_devices.items()]
                res = {"status": "ok", "devices": devs}
            elif action == "set_slot":
                path, new_slot = req.get("path"), req.get("slot")
                if path in self.phys_devices and 0 <= new_slot <= 3:
                    old_slot = self.phys_devices[path]["slot"]
                    for p, info in self.phys_devices.items():
                        if p != path and info["slot"] == new_slot:
                            self.phys_devices[p]["slot"] = old_slot
                    self.phys_devices[path]["slot"] = new_slot
                    res = {"status": "ok"}
            
            writer.write(json.dumps(res).encode())
            await writer.drain()
        except Exception: pass
        finally: writer.close()

async def main():
    manager = VirtualGamepadManager()
    if os.path.exists(SOCKET_PATH): os.remove(SOCKET_PATH)
    server = await asyncio.start_unix_server(manager.handle_ipc, path=SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o666)
    await asyncio.gather(manager.scan_devices(), server.serve_forever())

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass

