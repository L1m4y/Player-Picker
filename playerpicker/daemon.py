"""Player Picker daemon."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import signal
import socket
import stat
import sys
from pathlib import Path
from typing import Any

from evdev import AbsInfo, InputDevice, UInput
from evdev import ecodes as ecodes_module

from . import __version__
from .absmap import AbsAxis
from .config import ConfigError, parse_slot_count, socket_path
from .protocol import (
    MAX_MESSAGE_BYTES,
    ProtocolError,
    decode_message,
    encode_message,
    error_response,
    ok_response,
    validate_request,
)
from .slots import SlotError, SlotTable

LOG = logging.getLogger("playerpicker.daemon")
SCAN_INTERVAL = 1.0
IPC_TIMEOUT = 2.0
SOCKET_MODE = 0o666

VIRTUAL_VENDOR = 0x045E
VIRTUAL_PRODUCT = 0x028E
VIRTUAL_VERSION = 0x0110
VIRTUAL_BUSTYPE = 0x03

ABS_RANGES = {
    ecodes_module.ABS_X: (-32768, 32767, 16, 128),
    ecodes_module.ABS_Y: (-32768, 32767, 16, 128),
    ecodes_module.ABS_RX: (-32768, 32767, 16, 128),
    ecodes_module.ABS_RY: (-32768, 32767, 16, 128),
    ecodes_module.ABS_Z: (0, 255, 0, 0),
    ecodes_module.ABS_RZ: (0, 255, 0, 0),
    ecodes_module.ABS_HAT0X: (-1, 1, 0, 0),
    ecodes_module.ABS_HAT0Y: (-1, 1, 0, 0),
}

_BUTTON_NAMES = (
    "BTN_SOUTH",
    "BTN_EAST",
    "BTN_NORTH",
    "BTN_WEST",
    "BTN_A",
    "BTN_B",
    "BTN_X",
    "BTN_Y",
    "BTN_TL",
    "BTN_TR",
    "BTN_TL2",
    "BTN_TR2",
    "BTN_SELECT",
    "BTN_START",
    "BTN_MODE",
    "BTN_BACK",
    "BTN_THUMBL",
    "BTN_THUMBR",
    "BTN_DPAD_UP",
    "BTN_DPAD_DOWN",
    "BTN_DPAD_LEFT",
    "BTN_DPAD_RIGHT",
)

VIRTUAL_KEYS = tuple(
    dict.fromkeys(
        getattr(ecodes_module, name) for name in _BUTTON_NAMES if hasattr(ecodes_module, name)
    )
)
VIRTUAL_KEY_SET = frozenset(VIRTUAL_KEYS)
VIRTUAL_ABS_RANGES = {code: (values[0], values[1]) for code, values in ABS_RANGES.items()}
VIRTUAL_CAPABILITIES = {
    ecodes_module.EV_KEY: list(VIRTUAL_KEYS),
    ecodes_module.EV_ABS: [
        (code, AbsInfo(value=0, min=low, max=high, fuzz=fuzz, flat=flat, resolution=0))
        for code, (low, high, fuzz, flat) in ABS_RANGES.items()
    ],
}

_GAMEPAD_BUTTON_NAMES = (
    "BTN_SOUTH",
    "BTN_GAMEPAD",
    "BTN_A",
    "BTN_EAST",
    "BTN_B",
    "BTN_NORTH",
    "BTN_X",
    "BTN_WEST",
    "BTN_Y",
    "BTN_JOYSTICK",
    "BTN_TRIGGER",
    "BTN_TL",
    "BTN_TR",
)
GAMEPAD_BUTTONS = {
    getattr(ecodes_module, name) for name in _GAMEPAD_BUTTON_NAMES if hasattr(ecodes_module, name)
}
_KEYBOARD_KEYS = {
    getattr(ecodes_module, name)
    for name in ("KEY_A", "KEY_ENTER", "KEY_SPACE", "KEY_LEFTSHIFT")
    if hasattr(ecodes_module, name)
}

VIRTUAL_NAME_PREFIX = "Player Picker Slot"
VIRTUAL_PHYS_PREFIX = "playerpicker/"


class DaemonError(RuntimeError):
    pass


class AlreadyRunning(DaemonError):
    pass


def is_virtual_device(device: InputDevice) -> bool:
    name = device.name or ""
    phys = device.phys or ""
    return (
        name.startswith(VIRTUAL_NAME_PREFIX)
        or name.startswith("Virtual Gamepad")
        or phys.startswith(VIRTUAL_PHYS_PREFIX)
    )


def is_gamepad(device: InputDevice) -> bool:
    if is_virtual_device(device):
        return False
    capabilities = device.capabilities()
    keys = set(capabilities.get(ecodes_module.EV_KEY, ()))
    if not keys:
        return False
    if keys & _KEYBOARD_KEYS:
        return False
    return bool(keys & GAMEPAD_BUTTONS)


class VirtualGamepad:
    def __init__(self, index: int) -> None:
        self.index = index
        self._ui = UInput(
            VIRTUAL_CAPABILITIES,
            name=f"{VIRTUAL_NAME_PREFIX} {index + 1}",
            vendor=VIRTUAL_VENDOR,
            product=VIRTUAL_PRODUCT,
            version=VIRTUAL_VERSION,
            bustype=VIRTUAL_BUSTYPE,
            phys=f"{VIRTUAL_PHYS_PREFIX}slot{index + 1}",
        )

    def write(self, event_type: int, code: int, value: int) -> None:
        self._ui.write(event_type, code, value)

    def sync(self) -> None:
        self._ui.syn()

    def reset(self) -> None:
        for code in VIRTUAL_KEYS:
            self.write(ecodes_module.EV_KEY, code, 0)
        for code, (low, high) in VIRTUAL_ABS_RANGES.items():
            self.write(ecodes_module.EV_ABS, code, 0 if low <= 0 <= high else low)
        self.sync()

    def close(self) -> None:
        self._ui.close()


class PlayerPickerDaemon:
    def __init__(self, path: str, slot_count: int) -> None:
        self.socket_path = Path(path)
        self.slots = SlotTable(slot_count)
        self._virtuals: list[VirtualGamepad] = []
        self._devices: dict[str, InputDevice] = {}
        self._axes: dict[str, dict[int, AbsAxis]] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._deferred: set[str] = set()
        self._stop = asyncio.Event()

        try:
            for index in range(slot_count):
                self._virtuals.append(VirtualGamepad(index))
        except OSError as exc:
            self.close()
            raise DaemonError("cannot create virtual gamepads; check /dev/uinput access") from exc
        LOG.info("created %d virtual slot(s)", slot_count)

    def stop(self) -> None:
        self._stop.set()

    def close(self) -> None:
        for path in list(self._devices):
            device = self._devices.pop(path, None)
            self._axes.pop(path, None)
            slot = self.slots.remove(path)
            if slot is not None:
                with contextlib.suppress(OSError):
                    self._virtuals[slot].reset()
            if device is not None:
                with contextlib.suppress(OSError):
                    device.ungrab()
                with contextlib.suppress(OSError):
                    device.close()
        for gamepad in self._virtuals:
            with contextlib.suppress(OSError):
                gamepad.close()
        self._virtuals.clear()

    def _reset_slot(self, slot: int) -> None:
        if 0 <= slot < len(self._virtuals):
            with contextlib.suppress(OSError):
                self._virtuals[slot].reset()

    def _build_axis_map(self, device: InputDevice) -> dict[int, AbsAxis]:
        axes: dict[int, AbsAxis] = {}
        try:
            capabilities = device.capabilities(absinfo=True)
        except OSError:
            return axes
        for entry in capabilities.get(ecodes_module.EV_ABS, ()):
            if not isinstance(entry, tuple) or len(entry) != 2:
                continue
            code, info = entry
            target = ABS_RANGES.get(code)
            if target is None:
                continue
            axes[code] = AbsAxis(
                code=code,
                src_min=int(info.min),
                src_max=int(info.max),
                dst_min=target[0],
                dst_max=target[1],
            )
        return axes

    def _forward(self, path: str, event: Any) -> None:
        slot = self.slots.slot_of(path)
        if slot is None or not 0 <= slot < len(self._virtuals):
            return
        gamepad = self._virtuals[slot]

        if event.type == ecodes_module.EV_SYN:
            if event.code == ecodes_module.SYN_DROPPED:
                gamepad.reset()
            elif event.code == ecodes_module.SYN_REPORT:
                gamepad.sync()
            return

        if event.type == ecodes_module.EV_KEY:
            if event.code in VIRTUAL_KEY_SET:
                gamepad.write(ecodes_module.EV_KEY, event.code, event.value)
            return

        if event.type == ecodes_module.EV_ABS:
            axis = self._axes.get(path, {}).get(event.code)
            if axis is not None:
                gamepad.write(ecodes_module.EV_ABS, event.code, axis.scale(event.value))

    async def _run_device(self, path: str, device: InputDevice) -> None:
        try:
            slot = self.slots.add(path, device.name or Path(path).name)
            if slot is None:
                self._deferred.add(path)
                LOG.warning("all %d slots are in use; %s stays idle", self.slots.count, path)
                return

            try:
                device.grab()
            except OSError as exc:
                self.slots.remove(path)
                LOG.warning("cannot grab %s: %s", path, exc)
                return

            self._devices[path] = device
            self._axes[path] = self._build_axis_map(device)
            self._reset_slot(slot)
            LOG.info("attached %s (%s) to slot %d", path, device.name, slot + 1)

            async for event in device.async_read_loop():
                self._forward(path, event)
        except OSError as exc:
            LOG.info("%s disconnected: %s", path, exc)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOG.exception("unexpected error while handling %s", path)
        finally:
            self._detach(path)

    def _detach(self, path: str) -> None:
        device = self._devices.pop(path, None)
        self._axes.pop(path, None)
        slot = self.slots.remove(path)
        if slot is not None:
            self._reset_slot(slot)
        if device is not None:
            with contextlib.suppress(OSError):
                device.ungrab()
            with contextlib.suppress(OSError):
                device.close()
            LOG.info("detached %s (slot %d)", path, slot + 1)
        else:
            LOG.info("detached %s", path)

    async def _scan_devices(self) -> None:
        import evdev as evdev_module

        known: set[str] = set()
        while True:
            current = set(evdev_module.list_devices())
            for path in list(self._deferred):
                if path not in current or self.slots.free_slot() is None:
                    continue
                known.discard(path)
                self._deferred.discard(path)

            for path in sorted(current - known):
                try:
                    device = InputDevice(path)
                except OSError as exc:
                    LOG.debug("cannot open %s yet: %s", path, exc)
                    continue
                try:
                    virtual_or_ignored = is_virtual_device(device) or not is_gamepad(device)
                except OSError as exc:
                    LOG.debug("cannot inspect %s: %s", path, exc)
                    device.close()
                    continue
                if virtual_or_ignored:
                    device.close()
                    known.add(path)
                    continue

                known.add(path)
                task = asyncio.create_task(self._run_device(path, device), name=f"gamepad:{path}")
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

            known &= current
            self._deferred &= current
            await asyncio.sleep(SCAN_INTERVAL)

    def _dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            action = validate_request(request)
        except ProtocolError as exc:
            return error_response(str(exc))

        if action == "get_state":
            return ok_response(
                devices=self.slots.snapshot(), slots=self.slots.count, version=__version__
            )

        if action == "set_slot":
            path = request.get("path")
            if not isinstance(path, str) or not path:
                return error_response("'path' must be a non-empty string")
            try:
                changed = self.slots.move(path, request.get("slot"))
            except SlotError as exc:
                return error_response(str(exc))
            for slot in changed:
                self._reset_slot(slot)
            return ok_response(slot=request.get("slot"))

        return error_response(f"unknown action: {action}")

    async def _handle_ipc(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        response: dict[str, Any] | None = None
        try:
            raw = await asyncio.wait_for(reader.read(MAX_MESSAGE_BYTES), timeout=IPC_TIMEOUT)
            if raw:
                response = self._dispatch(decode_message(raw))
        except ProtocolError as exc:
            response = error_response(str(exc))
        except (TimeoutError, ConnectionError, OSError) as exc:
            LOG.debug("IPC connection failed: %s", exc)
        except Exception:
            LOG.exception("unexpected IPC error")
            response = error_response("internal daemon error")
        finally:
            if response is not None:
                try:
                    writer.write(encode_message(response))
                    await writer.drain()
                except (OSError, ProtocolError) as exc:
                    LOG.debug("could not send IPC response: %s", exc)
            writer.close()
            with contextlib.suppress(OSError, ConnectionError):
                await writer.wait_closed()

    async def run(self) -> None:
        server = await start_server(self.socket_path, self._handle_ipc)
        LOG.info("listening on %s", self.socket_path)

        scan_task = asyncio.create_task(self._scan_devices(), name="device-scan")
        try:
            await self._stop.wait()
            LOG.info("shutting down")
        finally:
            scan_task.cancel()
            for task in list(self._tasks):
                task.cancel()
            await asyncio.gather(scan_task, *self._tasks, return_exceptions=True)
            self.close()
            server.close()
            with contextlib.suppress(OSError):
                await server.wait_closed()
            with contextlib.suppress(OSError):
                if self.socket_path.is_socket():
                    self.socket_path.unlink()


def _socket_is_live(path: Path) -> bool:
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.settimeout(0.25)
    try:
        probe.connect(str(path))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def prepare_socket(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(mode):
        raise DaemonError(f"{path} exists and is not a Unix socket")
    if _socket_is_live(path):
        raise AlreadyRunning(f"another Player Picker daemon is already listening on {path}")
    try:
        path.unlink()
    except OSError as exc:
        raise DaemonError(f"cannot remove stale socket {path}: {exc}") from exc


async def start_server(path: Path, handler: Any) -> asyncio.AbstractServer:
    prepare_socket(path)
    try:
        server = await asyncio.start_unix_server(handler, path=str(path))
    except OSError as exc:
        raise DaemonError(f"cannot listen on {path}: {exc}") from exc
    try:
        os.chmod(path, SOCKET_MODE)
    except OSError as exc:
        LOG.warning("could not set socket permissions on %s: %s", path, exc)
    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="playerpicker-daemon",
        description="Expose physical gamepads as fixed virtual controller slots.",
    )
    parser.add_argument(
        "--socket", metavar="PATH", help="Unix socket path (environment: PLAYER_PICKER_SOCKET)"
    )
    parser.add_argument(
        "--slots",
        type=int,
        metavar="N",
        help="number of virtual slots (environment: PLAYER_PICKER_SLOTS)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="logging verbosity (default: INFO)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s: %(message)s")

    try:
        slot_count = parse_slot_count(
            args.slots if args.slots is not None else os.environ.get("PLAYER_PICKER_SLOTS")
        )
    except ConfigError as exc:
        parser.error(str(exc))
        return 2

    path = args.socket or socket_path()
    LOG.info("Player Picker daemon %s (%d slot(s))", __version__, slot_count)

    daemon: PlayerPickerDaemon | None = None
    try:
        daemon = PlayerPickerDaemon(path, slot_count)
    except DaemonError as exc:
        LOG.error("%s", exc)
        return 1

    async def runner() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError, RuntimeError):
                loop.add_signal_handler(sig, daemon.stop)
        await daemon.run()

    try:
        asyncio.run(runner())
    except AlreadyRunning as exc:
        LOG.error("%s", exc)
        daemon.close()
        return 1
    except DaemonError as exc:
        LOG.error("%s", exc)
        daemon.close()
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
