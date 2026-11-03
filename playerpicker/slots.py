"""Pure slot bookkeeping, kept free of evdev so it can be unit tested."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SlotError(ValueError):
    """Raised when a device cannot be registered or moved."""


@dataclass
class DeviceSlot:
    path: str
    name: str
    slot: int


class SlotTable:
    def __init__(self, slot_count: int) -> None:
        if isinstance(slot_count, bool) or not isinstance(slot_count, int) or slot_count < 1:
            raise ValueError("slot_count must be a positive integer")
        self._slot_count = slot_count
        self._devices: dict[str, DeviceSlot] = {}

    @property
    def count(self) -> int:
        return self._slot_count

    def __len__(self) -> int:
        return len(self._devices)

    def get(self, path: str) -> DeviceSlot | None:
        return self._devices.get(path)

    def slot_of(self, path: str) -> int | None:
        device = self._devices.get(path)
        return device.slot if device is not None else None

    def free_slot(self) -> int | None:
        used = {device.slot for device in self._devices.values()}
        for slot in range(self._slot_count):
            if slot not in used:
                return slot
        return None

    def add(self, path: str, name: str) -> int | None:
        if path in self._devices:
            raise SlotError(f"device is already registered: {path}")
        slot = self.free_slot()
        if slot is None:
            return None
        self._devices[path] = DeviceSlot(path=path, name=name, slot=slot)
        return slot

    def remove(self, path: str) -> int | None:
        device = self._devices.pop(path, None)
        return device.slot if device is not None else None

    def move(self, path: str, target: int) -> set[int]:
        device = self._devices.get(path)
        if device is None:
            raise SlotError(f"unknown device: {path}")
        if isinstance(target, bool) or not isinstance(target, int):
            raise SlotError("slot must be an integer")
        if not 0 <= target < self._slot_count:
            raise SlotError(f"slot must be between 0 and {self._slot_count - 1}")

        if device.slot == target:
            return set()

        source = device.slot
        occupant = self.device_at(target)
        if occupant is not None:
            occupant.slot = source
        device.slot = target
        return {source, target}

    def device_at(self, slot: int) -> DeviceSlot | None:
        for device in self._devices.values():
            if device.slot == slot:
                return device
        return None

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {"path": device.path, "name": device.name, "slot": device.slot}
            for device in sorted(self._devices.values(), key=lambda item: item.slot)
        ]
