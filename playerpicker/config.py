"""Configuration shared by the daemon and the graphical interface."""

from __future__ import annotations

import logging
import os
import sysconfig
from collections.abc import Mapping
from pathlib import Path

LOG = logging.getLogger(__name__)

DEFAULT_SOCKET_PATH = "/run/joy_slot.sock"
DEFAULT_SLOT_COUNT = 4
MIN_SLOT_COUNT = 1
MAX_SLOT_COUNT = 8

SOCKET_ENV = "PLAYER_PICKER_SOCKET"
SLOTS_ENV = "PLAYER_PICKER_SLOTS"
ICONS_ENV = "PLAYER_PICKER_ICONS"

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent


class ConfigError(ValueError):
    """Raised when a configuration value is not valid."""


def parse_slot_count(value: str | int | None, *, default: int = DEFAULT_SLOT_COUNT) -> int:
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ConfigError(
            f"{SLOTS_ENV} must be an integer between {MIN_SLOT_COUNT} and {MAX_SLOT_COUNT}"
        )
    try:
        count = int(value)
    except (TypeError, ValueError):
        raise ConfigError(
            f"{SLOTS_ENV} must be an integer between {MIN_SLOT_COUNT} and {MAX_SLOT_COUNT}"
        ) from None
    if not MIN_SLOT_COUNT <= count <= MAX_SLOT_COUNT:
        raise ConfigError(
            f"{SLOTS_ENV} must be an integer between {MIN_SLOT_COUNT} and {MAX_SLOT_COUNT}"
        )
    return count


def socket_path(env: Mapping[str, str] | None = None) -> str:
    values = os.environ if env is None else env
    configured = values.get(SOCKET_ENV, "").strip()
    return configured or DEFAULT_SOCKET_PATH


def resolve_icon_dir(env: Mapping[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    override = values.get(ICONS_ENV, "").strip()
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_dir():
            return candidate
        LOG.warning("%s points to a missing directory: %s", ICONS_ENV, candidate)

    candidates = [
        REPO_ROOT / "icons",
        Path(sysconfig.get_path("data")) / "share" / "playerpicker" / "icons",
        Path("/usr/share/playerpicker/icons"),
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return REPO_ROOT / "icons"
