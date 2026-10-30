#!/usr/bin/env python3
import sys
import json
import os
import socket
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSystemTrayIcon, QMenu)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor, QIcon, QPixmap

SOCKET_PATH = os.environ.get("PLAYER_PICKER_SOCKET", "/run/joy_slot.sock")
ICONS_DIR = os.environ.get("PLAYER_PICKER_ICONS") or str(Path(__file__).resolve().parent / "icons")

class SlotCard(QFrame):
    clicked = pyqtSignal(int)
    def __init__(self, slot_index, parent=None):
        super().__init__(parent)
        self.slot_index = slot_index
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.slot_index)

class JoySlotGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("A simple tool to reassign controller positions!")
        self.setFixedSize(850, 460) 
        
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMinimizeButtonHint)
        
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(f"{ICONS_DIR}/tray.png"))

        self.tray_menu = QMenu()
        self.show_action = self.tray_menu.addAction("Show Panel")
        self.show_action.triggered.connect(self.show_app)
        self.quit_action = self.tray_menu.addAction("Quit")
        self.quit_action.triggered.connect(self.real_quit)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.tray_activated)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 30, 30, 20)
        self.layout.setSpacing(15)
        
        title_label = QLabel()
        title_pix = QPixmap(os.path.join(ICONS_DIR, "title.png"))
        title_label.setPixmap(title_pix.scaledToHeight(100, Qt.TransformationMode.SmoothTransformation))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(title_label)
        
        self.status_label = QLabel("Connecting to system...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Noto Sans", 11))
        self.layout.addWidget(self.status_label)
        
        self.cards_layout = QHBoxLayout()
        self.cards_layout.setSpacing(20)
        self.layout.addLayout(self.cards_layout)
        
        self.slots_ui = []
        for i in range(4):
            card = SlotCard(i)
            card.setObjectName(f"card_{i}")
            card_layout = QVBoxLayout(card)
            card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.setSpacing(10)
            
            lbl_title = QLabel(f"Controller {i+1}")
            lbl_title.setFont(QFont("Noto Sans", 16, QFont.Weight.Bold))
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            lbl_icon = QLabel()
            pixmap = QPixmap(f"{ICONS_DIR}/controller.png")
            lbl_icon.setPixmap(pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
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
            
            lbl_desc = QLabel("Free")
            lbl_desc.setFont(QFont("Noto Sans", 10))
            lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_desc.setWordWrap(True)
            
            card_layout.addWidget(lbl_title)
            card_layout.addSpacing(10)
            card_layout.addWidget(lbl_icon)
            card_layout.addSpacing(10)
            card_layout.addWidget(status_container)
            card_layout.addWidget(lbl_desc)
            
            card.status_icon = status_icon
            card.status_text = status_text
            card.lbl_desc = lbl_desc
            card.is_assigned = False
            card.device_path = None
            
            card.clicked.connect(self.on_slot_clicked)
            self.cards_layout.addWidget(card)
            self.slots_ui.append(card)
            
        self.layout.addStretch()
        
        footer = QLabel("Created by L1m4y under GPL license (￣▽￣)/")
        footer.setFont(QFont("Noto Sans", 10))
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: palette(text); opacity: 0.1;")
        self.layout.addWidget(footer)
        
        self.selected_path = None
        self.selected_slot = None
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_devices)
        self.timer.start(500)
        self.refresh_devices()

    def show_app(self):
        self.showNormal()
        self.activateWindow()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_app()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def real_quit(self):
        QApplication.quit()

    def send_ipc(self, payload):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(SOCKET_PATH)
                s.sendall(json.dumps(payload).encode())
                return json.loads(s.recv(4096).decode())
        except Exception:
            return None

    def refresh_devices(self):
        resp = self.send_ipc({"action": "get_state"})
        if not resp or resp.get("status") != "ok":
            self.status_label.setText("Error: System daemon is not running.")
            for card in self.slots_ui: self.update_card_ui(card, False, None)
            self.apply_styles()
            return
            
        if self.selected_path:
            self.status_label.setText("Select target controller... (click again to cancel)")
        else:
            self.status_label.setText("System active. Click a controller to move it.")
        
        devices = resp.get("devices", [])
        slot_map = {i: None for i in range(4)}
        for dev in devices:
            if 0 <= dev["slot"] <= 3: slot_map[dev["slot"]] = dev
        
        for i, card in enumerate(self.slots_ui):
            dev = slot_map[i]
            if dev: self.update_card_ui(card, True, dev["name"], dev["path"])
            else: self.update_card_ui(card, False, None, None)

        self.apply_styles()

    def update_card_ui(self, card, is_assigned, name, path=None):
        card.is_assigned = is_assigned
        card.device_path = path
        if is_assigned:
            card.status_icon.setPixmap(QPixmap(f"{ICONS_DIR}/check.svg").scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            card.status_text.setText("Active")
            card.lbl_desc.setText(f"{name}")
        else:
            card.status_icon.setPixmap(QPixmap(f"{ICONS_DIR}/delete.svg").scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            card.status_text.setText("Inactive")
            card.lbl_desc.setText("Free")

    def apply_styles(self):
        for i, card in enumerate(self.slots_ui):
            if card.is_assigned:
                bg_color = "rgba(128, 128, 128, 0.1)"
                border = "1px solid palette(highlight)"
            else:
                bg_color = "transparent"
                border = "1px solid palette(midlight)"
            
            if self.selected_slot == i:
                bg_color = "rgba(128, 128, 128, 0.2)"
                border = "2px solid palette(highlight)"
                
            card.setStyleSheet(f"QFrame#card_{i} {{ background-color: {bg_color}; border: {border}; border-radius: 12px; }} QFrame#card_{i}:hover {{ background-color: rgba(128, 128, 128, 0.15); }}")

    def on_slot_clicked(self, slot_index):
        clicked_card = self.slots_ui[slot_index]
        
        if self.selected_path is None:
            if clicked_card.is_assigned:
                self.selected_path = clicked_card.device_path
                self.selected_slot = slot_index
                self.refresh_devices()
        else:
            if self.selected_slot != slot_index:
                self.send_ipc({"action": "set_slot", "path": self.selected_path, "slot": slot_index})
            self.selected_path = None
            self.selected_slot = None
            self.refresh_devices()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setApplicationName("playerpicker")
    app.setDesktopFileName("playerpicker.desktop")
    
    app.setWindowIcon(QIcon(f"{ICONS_DIR}/icon.png"))
    app.setQuitOnLastWindowClosed(False)
    
    window = JoySlotGUI()
    window.show()
    sys.exit(app.exec())

