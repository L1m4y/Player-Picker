"""Absolute-axis scaling for virtual gamepads."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AbsAxis:
    """Map a source axis range onto the range exposed by the virtual device."""

    code: int
    src_min: int
    src_max: int
    dst_min: int
    dst_max: int

    def scale(self, value: int) -> int:
        if self.src_max <= self.src_min:
            return self.dst_min if value <= self.src_min else self.dst_max
        if (self.src_min, self.src_max) == (self.dst_min, self.dst_max):
            return max(self.src_min, min(self.src_max, value))

        clamped = max(self.src_min, min(self.src_max, value))
        ratio = (clamped - self.src_min) / (self.src_max - self.src_min)
        return round(self.dst_min + ratio * (self.dst_max - self.dst_min))
