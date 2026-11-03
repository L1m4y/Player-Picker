"""PyQt6 interface for Player Picker."""

from __future__ import annotations

import argparse
import logging
import os
import queue
import sys
import threading
import time

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from . import APP_ID, APP_NAME, __version__
from .config import (
    MAX_SLOT_COUNT,
    MIN_SLOT_COUNT,
    SLOTS_ENV,
    SOCKET_ENV,
    ConfigError,
    parse_slot_count,
    resolve_icon_dir,
    socket_path,
)
from .protocol import ProtocolError, send_request

LOG = logging.getLogger("playerpicker.gui")

POLL_INTERVAL = 0.5
REQUEST_TIMEOUT = 0.75
TRAY_HINT_SECONDS = 5.0


class DaemonWorker(QThread):
    state_ready = pyqtSignal(object)
    action_done = pyqtSignal(str)
    action_failed = pyqtSignal(str)
    connection_failed = pyqtSignal(str)

    def __init__(self, socket_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._socket_path = socket_path
        self._requests: queue.Queue[dict] = queue.Queue()
        self._stop = threading.Event()
        self._wake = threading.Event()

    def submit(self, payload: dict) -> None:
        self._requests.put(payload)
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def _request_state(self) -> None:
        response = send_request(
            self._socket_path,
            {"action": "get_state"},
            timeout=REQUEST_TIMEOUT,
        )
        self.state_ready.emit(response)

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                payload = self._requests.get_nowait()
            except queue.Empty:
                payload = {"action": "get_state"}

            try:
                response = send_request(self._socket_path, payload, timeout=REQUEST_TIMEOUT)
            except (OSError, ProtocolError) as exc:
                self.connection_failed.emit(str(exc))
            else:
                if response.get("status") == "ok":
                    if payload.get("action") == "get_state":
                        self.state_ready.emit(response)
                    else:
                        self.action_done.emit("Controller moved.")
                        try:
                            self._request_state()
                        except (OSError, ProtocolError) as exc:
                            self.connection_failed.emit(str(exc))
                else:
                    message = response.get("error") or "the daemon rejected the request"
                    self.action_failed.emit(str(message))

            self._wake.wait(POLL_INTERVAL)
            self._wake.clear()


class SlotCard(QFrame):
    clicked = pyqtSignal(int)

    def __init__(self, slot_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slot_index = slot_index
        self.is_assigned = False
        self.device_path: str | None = None
        self._render_key: tuple[bool, str | None, str | None] | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Controller slot {slot_index + 1}")
        self.setMinimumSize(165, 205)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.slot_index)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit(self.slot_index)
            event.accept()
            return
        super().keyPressEvent(event)


class PlayerPickerWindow(QWidget):
    def __init__(
        self,
        daemon_socket: str,
        slot_count: int,
        *,
        tray_available: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._socket_path = daemon_socket
        self._slot_count = 0
        self._connected = False
        self._selected_path: str | None = None
        self._selected_slot: int | None = None
        self._notice = ""
        self._notice_until = 0.0
        self._tray_hint_shown = False
        self._style_keys: list[tuple[bool, bool]] = []

        self._icon_dir = resolve_icon_dir()
        self._title_pixmap = self._load_pixmap("title.png", height=100)
        self._controller_pixmap = self._load_pixmap("controller.png", width=80, height=80)
        self._check_pixmap = self._load_pixmap("check.svg", width=18, height=18)
        self._delete_pixmap = self._load_pixmap("delete.svg", width=18, height=18)
        self._app_icon = self._load_icon("icon.png")

        self.setWindowTitle(APP_NAME)
        if not self._app_icon.isNull():
            self.setWindowIcon(self._app_icon)
        self.resize(920, 540)
        self.setMinimumSize(760, 480)

        if tray_available:
            self._build_tray()

        self._build_layout()
        self._rebuild_cards(slot_count)
        self.apply_styles()
        self._update_status_text()

        self.worker = DaemonWorker(self._socket_path, self)
        self.worker.state_ready.connect(self._on_state)
        self.worker.action_done.connect(self._on_action_done)
        self.worker.action_failed.connect(self._on_action_failed)
        self.worker.connection_failed.connect(self._on_connection_failed)
        self.worker.start()

    def _build_layout(self) -> None:
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(30, 30, 30, 20)
        self.root_layout.setSpacing(15)

        title_label = QLabel()
        if self._title_pixmap is not None:
            title_label.setPixmap(self._title_pixmap)
        else:
            title_label.setText(APP_NAME)
            title_label.setFont(QFont("Noto Sans", 24, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.root_layout.addWidget(title_label)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Noto Sans", 11))
        self.status_label.setWordWrap(True)
        self.root_layout.addWidget(self.status_label)

        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(18)
        self.root_layout.addLayout(self.cards_layout)
        self.root_layout.addStretch()

        footer_label = QLabel(f"{APP_NAME} {__version__} · Created by L1m4y · GPL-3.0")
        footer_label.setFont(QFont("Noto Sans", 10))
        footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_label.setStyleSheet("color: palette(mid);")
        self.root_layout.addWidget(footer_label)

    def _build_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        icon = self._app_icon
        if icon.isNull():
            icon = QIcon.fromTheme("input-gaming")
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip(APP_NAME)

        self.tray_menu = QMenu()
        show_action = self.tray_menu.addAction("Show panel")
        show_action.triggered.connect(self.show_app)
        quit_action = self.tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.real_quit)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def _load_pixmap(
        self,
        name: str,
        *,
        width: int | None = None,
        height: int | None = None,
    ) -> QPixmap | None:
        pixmap = QPixmap(str(self._icon_dir / name))
        if pixmap.isNull():
            return None
        if width is not None and height is not None:
            pixmap = pixmap.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        elif height is not None:
            pixmap = pixmap.scaledToHeight(
                height,
                Qt.TransformationMode.SmoothTransformation,
            )
        return pixmap

    def _load_icon(self, name: str) -> QIcon:
        path = self._icon_dir / name
        return QIcon(str(path)) if path.is_file() else QIcon()

    def _rebuild_cards(self, slot_count: int) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.slots_ui: list[SlotCard] = []
        self._style_keys = []
        self._slot_count = slot_count
        columns = min(4, slot_count)

        for index in range(slot_count):
            card = SlotCard(index)
            card.setObjectName(f"card_{index}")

            layout = QVBoxLayout(card)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.setSpacing(8)

            title = QLabel(f"Controller {index + 1}")
            title.setFont(QFont("Noto Sans", 16, QFont.Weight.Bold))
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)

            icon = QLabel()
            if self._controller_pixmap is not None:
                icon.setPixmap(self._controller_pixmap)
            else:
                icon.setText("Gamepad")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            status_container = QWidget()
            status_layout = QHBoxLayout(status_container)
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_layout.setSpacing(8)

            status_icon = QLabel()
            status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_text = QLabel("Inactive")
            status_text.setFont(QFont("Noto Sans", 12, QFont.Weight.Bold))
            status_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_layout.addWidget(status_icon)
            status_layout.addWidget(status_text)

            description = QLabel("Free")
            description.setFont(QFont("Noto Sans", 10))
            description.setAlignment(Qt.AlignmentFlag.AlignCenter)
            description.setWordWrap(True)

            layout.addWidget(title)
            layout.addWidget(icon)
            layout.addWidget(status_container)
            layout.addWidget(description)

            card.status_icon = status_icon
            card.status_text = status_text
            card.lbl_desc = description
            card.clicked.connect(self.on_slot_clicked)
            card.setToolTip("Free slot")
            self.cards_layout.addWidget(card, index // columns, index % columns)
            self.slots_ui.append(card)

        for column in range(columns):
            self.cards_layout.setColumnStretch(column, 1)

        self.setMinimumSize(
            max(760, columns * 190 + 80),
            480 if slot_count <= 4 else 760,
        )

        if (
            self._selected_path is not None
            and self._selected_slot is not None
            and self._selected_slot >= slot_count
        ):
            self._clear_selection()

    def _update_status_text(self) -> None:
        now = time.monotonic()
        if self._notice and now < self._notice_until:
            text = self._notice
        elif self._selected_path is not None:
            text = "Select a target slot, or click the same slot to cancel."
        elif self._connected:
            text = "System active. Click a controller to move it."
        else:
            text = "Waiting for the Player Picker daemon..."
        self.status_label.setText(text)

    def _set_notice(self, message: str, seconds: float = 3.0) -> None:
        self._notice = message
        self._notice_until = time.monotonic() + seconds
        self._update_status_text()

    def _clear_selection(self) -> None:
        self._selected_path = None
        self._selected_slot = None

    def _on_state(self, state: object) -> None:
        if not isinstance(state, dict) or state.get("status") != "ok":
            return
        self._connected = True

        reported_slots = state.get("slots")
        if (
            isinstance(reported_slots, int)
            and not isinstance(reported_slots, bool)
            and MIN_SLOT_COUNT <= reported_slots <= MAX_SLOT_COUNT
            and reported_slots != self._slot_count
        ):
            self._rebuild_cards(reported_slots)

        devices = state.get("devices")
        if not isinstance(devices, list):
            devices = []

        slot_map: dict[int, dict] = {}
        paths: set[str] = set()
        for device in devices:
            if not isinstance(device, dict):
                continue
            path = device.get("path")
            slot = device.get("slot")
            if (
                not isinstance(path, str)
                or not path
                or isinstance(slot, bool)
                or not isinstance(slot, int)
                or not 0 <= slot < len(self.slots_ui)
            ):
                continue
            slot_map[slot] = device
            paths.add(path)

        if self._selected_path is not None and self._selected_path not in paths:
            self._clear_selection()

        if self._selected_path is not None:
            for slot, device in slot_map.items():
                if device.get("path") == self._selected_path:
                    self._selected_slot = slot
                    break

        for index, card in enumerate(self.slots_ui):
            device = slot_map.get(index)
            if device is not None:
                name = str(device.get("name") or "Controller")
                self.update_card_ui(card, True, name, str(device.get("path") or ""))
            else:
                self.update_card_ui(card, False, None, None)

        self.apply_styles()
        self._update_status_text()

    def update_card_ui(
        self,
        card: SlotCard,
        is_assigned: bool,
        name: str | None,
        path: str | None = None,
    ) -> None:
        key = (is_assigned, name, path)
        if card._render_key == key:
            return
        card._render_key = key
        card.is_assigned = is_assigned
        card.device_path = path
        if is_assigned:
            if self._check_pixmap is not None:
                card.status_icon.clear()
                card.status_icon.setText("")
                card.status_icon.setPixmap(self._check_pixmap)
            else:
                card.status_icon.clear()
                card.status_icon.setText("OK")
            card.status_text.setText("Active")
            card.lbl_desc.setText(name or "Controller")
            card.setToolTip(name or "")
        else:
            if self._delete_pixmap is not None:
                card.status_icon.clear()
                card.status_icon.setText("")
                card.status_icon.setPixmap(self._delete_pixmap)
            else:
                card.status_icon.clear()
                card.status_icon.setText("Off")
            card.status_text.setText("Inactive")
            card.lbl_desc.setText("Free")
            card.setToolTip("Free slot")

    def apply_styles(self) -> None:
        for index, card in enumerate(self.slots_ui):
            key = (card.is_assigned, self._selected_slot == index)
            if index < len(self._style_keys):
                if self._style_keys[index] == key:
                    continue
                self._style_keys[index] = key
            else:
                self._style_keys.append(key)

            if key[1]:
                background = "rgba(128, 128, 128, 0.20)"
                border = "2px solid palette(highlight)"
            elif key[0]:
                background = "rgba(128, 128, 128, 0.10)"
                border = "1px solid palette(highlight)"
            else:
                background = "transparent"
                border = "1px solid palette(midlight)"

            card.setStyleSheet(
                f"QFrame#card_{index} {{"
                f" background-color: {background};"
                f" border: {border};"
                " border-radius: 12px;"
                " }"
                f" QFrame#card_{index}:hover {{"
                " background-color: rgba(128, 128, 128, 0.15);"
                " }"
                f" QFrame#card_{index}:focus {{"
                " border: 2px solid palette(highlight);"
                " }"
            )

    def on_slot_clicked(self, slot_index: int) -> None:
        card = self.slots_ui[slot_index]
        if self._selected_path is None:
            if card.is_assigned and card.device_path:
                self._selected_path = card.device_path
                self._selected_slot = slot_index
                self.apply_styles()
                self._update_status_text()
            else:
                self._set_notice("Select an active controller first.")
            return

        if self._selected_slot != slot_index:
            self.worker.submit(
                {"action": "set_slot", "path": self._selected_path, "slot": slot_index}
            )
            self._set_notice("Moving controller...", 2.0)
        else:
            self._set_notice("Selection cancelled.", 2.0)

        self._clear_selection()
        self.apply_styles()
        self._update_status_text()

    def _on_action_done(self, message: str) -> None:
        self._set_notice(message, 2.0)

    def _on_action_failed(self, message: str) -> None:
        self._set_notice(f"Could not move controller: {message}", 4.0)

    def _on_connection_failed(self, message: str) -> None:
        LOG.debug("daemon connection failed: %s", message)
        self._connected = False
        for card in self.slots_ui:
            self.update_card_ui(card, False, None, None)
        self.apply_styles()
        self._update_status_text()

    def show_app(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_app()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_app()

    def closeEvent(self, event) -> None:
        if getattr(self, "tray_icon", None) is not None and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.tray_icon.showMessage(
                    APP_NAME,
                    "Player Picker is still running in the system tray.",
                    QSystemTrayIcon.MessageIcon.Information,
                    int(TRAY_HINT_SECONDS * 1000),
                )
            return
        event.accept()
        self.real_quit()

    def shutdown(self) -> None:
        if getattr(self, "worker", None) is None:
            return
        self.worker.stop()
        self.worker.wait(3000)
        if getattr(self, "tray_icon", None) is not None:
            self.tray_icon.hide()

    def real_quit(self) -> None:
        self.shutdown()
        QApplication.quit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="playerpicker",
        description="Reassign physical gamepads to fixed virtual controller slots.",
    )
    parser.add_argument(
        "--socket",
        metavar="PATH",
        help=f"Unix socket path (environment: {SOCKET_ENV})",
    )
    parser.add_argument(
        "--slots",
        type=int,
        metavar="N",
        help=(
            f"initial slot count, {MIN_SLOT_COUNT}-{MAX_SLOT_COUNT} "
            f"(environment: {SLOTS_ENV}); the daemon value wins once connected"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, qt_args = parser.parse_known_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    try:
        slot_count = parse_slot_count(
            args.slots if args.slots is not None else os.environ.get(SLOTS_ENV)
        )
    except ConfigError as exc:
        parser.error(str(exc))

    daemon_socket = args.socket or socket_path()
    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(f"{APP_ID}.desktop")

    icon = QIcon(str(resolve_icon_dir() / "icon.png"))
    if not icon.isNull():
        app.setWindowIcon(icon)

    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    app.setQuitOnLastWindowClosed(not tray_available)

    window = PlayerPickerWindow(daemon_socket, slot_count, tray_available=tray_available)
    app.aboutToQuit.connect(window.shutdown)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
