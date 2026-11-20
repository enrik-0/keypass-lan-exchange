"""Windows GUI: explicitly initiated, one-off encrypted clipboard transfer."""
import hashlib
import socket
import sys
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QAction
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QVBoxLayout, QWidget, QSystemTrayIcon, QMenu, QStyle, QCheckBox, QInputDialog)

from aliases import AliasStore
from identity import get_identity, TrustStore
from network import Signals, Discovery, TransferService
from secure_protocol import raw_pub
from hotkey import WindowsHotkey, keepassxc_is_foreground, clipboard_sequence, copy_shortcut
from autostart import is_enabled, set_enabled
from clipboard_guard import ClipboardGuard


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.quitting = False
        self.setWindowTitle('KeePass LAN Share - transferencia puntual')
        self.resize(570, 345)
        self.signals = Signals()
        self.signals.question.connect(self.on_question)
        self.signals.discovered.connect(self.refresh_peers)
        self.signals.delivered.connect(self.update_status)
        self.signals.failure.connect(self.on_failure)
        self.trust = TrustStore()
        self.aliases = AliasStore()
        self.identity = get_identity()
        self.name = socket.gethostname()
        self.clipboard_token = None
        self.guard = ClipboardGuard()
        self.items = []

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addWidget(QLabel('Desde KeePassXC: selecciona una entrada y pulsa Ctrl+Alt+S.\nSolo se enviará la contraseña copiada con este atajo, si el portapapeles no ha cambiado desde entonces.'))
        info = QGroupBox('Transferencia de una sola vez')
        form = QFormLayout(info)
        self.devices = QComboBox()
        self.devices.setMinimumWidth(360)
        form.addRow('Equipo de destino:', self.devices)
        self.label = QLineEdit()
        self.label.setPlaceholderText('Referencia no sensible (p. ej., equipo de pruebas)')
        self.label.setMaxLength(80)
        form.addRow('Referencia:', self.label)
        layout.addWidget(info)
        row = QHBoxLayout()
        self.send_btn = QPushButton('Enviar contenido actual del portapapeles')
        self.send_btn.clicked.connect(self.send)
        row.addWidget(self.send_btn)
        layout.addLayout(row)
        layout.addWidget(QLabel('La contraseña no aparece en esta ventana. El destinatario debe aceptar el envío.'))
        self.status = QLabel('Iniciando descubrimiento…')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()
        self.autostart = QCheckBox('Iniciar con Windows (solo versión .exe)')
        self.autostart.setChecked(is_enabled())
        self.autostart.setEnabled(getattr(sys, 'frozen', False))
        self.autostart.toggled.connect(self.toggle_autostart)
        layout.addWidget(self.autostart)

        row2 = QHBoxLayout()
        self.rename = QPushButton('Renombrar equipo seleccionado')
        self.rename.clicked.connect(self.rename_peer)
        row2.addWidget(self.rename)
        self.forget = QPushButton('Olvidar un equipo emparejado')
        self.forget.clicked.connect(self.forget_peer)
        row2.addWidget(self.forget)
        row2.addStretch()
        layout.addLayout(row2)
        self.setCentralWidget(root)

        self.network = TransferService(self.signals, self.identity, self.name, self.trust)
        self.discovery = Discovery(self.signals, raw_pub(self.identity.public_key()), self.name)
        self.update_status('Buscando otros equipos en la red local…')
        self.tray = QSystemTrayIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), self)
        self.tray.setToolTip('KeePass LAN Share - Ctrl+Alt+S desde KeePassXC')
        menu = QMenu()
        open_action = QAction('Abrir KeePass LAN Share', self)
        open_action.triggered.connect(self.show_front)
        menu.addAction(open_action)
        exit_action = QAction('Salir', self)
        exit_action.triggered.connect(self.exit_program)
        menu.addAction(exit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()
        self.hotkey = WindowsHotkey()
        self.hotkey.activated.connect(self.on_hotkey)
        self.hotkey.error.connect(self.on_failure)
        self.hotkey.start()

    def toggle_autostart(self, checked):
        try:
            set_enabled(checked)
        except Exception as exc:
            self.autostart.blockSignals(True)
            self.autostart.setChecked(is_enabled())
            self.autostart.blockSignals(False)
            QMessageBox.warning(self, 'Inicio automático', str(exc))

    def show_front(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_front()

    def on_hotkey(self):
        # The shortcut is intentionally inert outside KeePassXC.
        if not keepassxc_is_foreground():
            return
        # Wait for the user to release Ctrl+Alt+S before sending Ctrl+C.
        QTimer.singleShot(400, self.copy_from_keepassxc)

    def copy_from_keepassxc(self):
        if not keepassxc_is_foreground():
            return
        if os.name != 'nt':
            return
        # Do not send Ctrl+C while modifiers from the global shortcut are held.
        import ctypes
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        if user32.GetAsyncKeyState(0x11) & 0x8000 or user32.GetAsyncKeyState(0x12) & 0x8000:
            self.tray.showMessage('KeePass LAN Share', 'Suelta Ctrl y Alt y vuelve a pulsar el atajo.')
            return
        previous = clipboard_sequence()
        copy_shortcut()
        QTimer.singleShot(350, lambda: self.after_copy(previous))

    def after_copy(self, previous):
        if clipboard_sequence() == previous or not QApplication.clipboard().text():
            self.guard.clear()
            self.tray.showMessage('KeePass LAN Share',
                'No se ha copiado una contraseña nueva. Selecciona una entrada en KeePassXC.')
            return
        # Record the clipboard state produced by this copy; any later change invalidates it.
        self.guard.mark(clipboard_sequence())
        # Never show the password in this interface.
        self.show_front()
        self.update_status('Contraseña copiada desde KeePassXC. Selecciona el equipo y pulsa Enviar.')

    def exit_program(self):
        self.quitting = True
        self.hotkey.stop()
        self.discovery.close()
        self.network.close()
        self.tray.hide()
        QApplication.instance().quit()

    def display_name(self, peer):
        alias = self.aliases.get(peer.ident)
        return alias or peer.host

    def refresh_peers(self, peers):
        previous = self.devices.currentData()
        prev_instance = previous.instance if previous else None
        self.items = sorted(peers, key=lambda p: self.display_name(p).lower())
        self.devices.clear()
        for peer in self.items:
            alias = self.aliases.get(peer.ident)
            text = f'{alias}  ({peer.host})  [{peer.ip}]' if alias else f'{peer.host}  [{peer.ip}]'
            self.devices.addItem(text, userData=peer)
            if peer.instance == prev_instance:
                self.devices.setCurrentIndex(self.devices.count() - 1)
        if not self.items:
            self.devices.addItem('Sin equipos disponibles', userData=None)

    def rename_peer(self):
        peer = self.devices.currentData()
        if not peer:
            QMessageBox.information(self, 'Renombrar equipo', 'Selecciona primero un equipo de la lista.')
            return
        current = self.aliases.get(peer.ident) or ''
        name, ok = QInputDialog.getText(self, 'Renombrar equipo',
            f'Nombre para {peer.host} (solo se ve en este PC; déjalo vacío para quitarlo):',
            text=current)
        if not ok:
            return
        self.aliases.set(peer.ident, name)
        self.refresh_peers(self.items)
        self.update_status(f'Equipo renombrado. Se muestra como «{self.aliases.get(peer.ident) or peer.host}».')

    def send(self):
        target = self.devices.currentData()
        if not target:
            QMessageBox.information(self, 'Sin equipos', 'Abre esta aplicación en el otro ordenador y comprueba la red y el firewall.')
            return
        if not self.guard.is_valid(clipboard_sequence()):
            QMessageBox.warning(self, 'Portapapeles cambiado',
                'El portapapeles ha cambiado desde que copiaste la contraseña en KeePassXC.\n'
                'Vuelve a seleccionar la entrada y pulsa Ctrl+Alt+S.')
            self.guard.clear()
            return
        label = self.label.text().strip() or 'Credencial de acceso'
        cb = QApplication.clipboard()
        secret = cb.text()
        if not secret:
            QMessageBox.warning(self, 'Portapapeles vacío', 'Copia primero la contraseña desde KeePassXC (Ctrl + C).')
            return
        if len(secret.encode('utf-8')) > 8192:
            QMessageBox.warning(self, 'Contenido largo', 'El texto no puede superar los 8192 bytes.')
            return
        answer = QMessageBox.question(self, 'Confirmar destinatario',
            f'¿Enviar la contraseña copiada desde KeePassXC a {self.display_name(target)} ({target.host}, {target.ip})?\n\n'
            'El contenido no se muestra en esta ventana ni se guarda en un historial.')
        if answer != QMessageBox.StandardButton.Yes:
            return
        # Re-check after the dialog: the clipboard may have changed while it was open.
        if not self.guard.is_valid(clipboard_sequence()):
            QMessageBox.warning(self, 'Portapapeles cambiado',
                'El portapapeles ha cambiado mientras confirmabas. No se ha enviado nada.')
            self.guard.clear()
            return
        self.guard.clear()
        self.send_btn.setEnabled(False)
        self.update_status('Estableciendo conexión cifrada…')
        self.network.send_secret(target, label, secret)
        # No secret is persisted in app state after dispatch; Python cannot ensure memory zeroization.
        del secret

    def on_question(self, req):
        if req.kind == 'clipboard':
            self.set_remote_clipboard(req.details)
            req.accepted = True
            req.event.set()
            return
        result = QMessageBox.question(self, req.title, req.details,
                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                     QMessageBox.StandardButton.No)
        req.accepted = result == QMessageBox.StandardButton.Yes
        req.event.set()

    def set_remote_clipboard(self, secret):
        cb = QGuiApplication.clipboard()
        mime = QMimeData()
        mime.setText(secret)
        # Windows clipboard formats to ask OS to exclude history/cloud processing.
        mime.setData('ExcludeClipboardContentFromMonitorProcessing', b'1')
        mime.setData('CanIncludeInClipboardHistory', b'0')
        mime.setData('CanUploadToCloudClipboard', b'0')
        cb.setMimeData(mime)
        fingerprint = hashlib.sha256(secret.encode('utf-8')).digest()
        self.clipboard_token = object()
        token = self.clipboard_token

        def clear_if_unchanged():
            if self.clipboard_token is not token:
                return
            current = cb.text()
            if hashlib.sha256(current.encode('utf-8')).digest() == fingerprint:
                cb.clear()
            self.clipboard_token = None

        QTimer.singleShot(20_000, clear_if_unchanged)

    def update_status(self, text):
        self.send_btn.setEnabled(True)
        self.status.setText(text)

    def on_failure(self, message):
        self.update_status(message)

    def forget_peer(self):
        if not self.trust.peers:
            QMessageBox.information(self, 'Equipos', 'No hay equipos emparejados.')
            return
        names = '\n'.join(f'{name}: {key[:12]}…' for key, name in self.trust.peers.items())
        response = QMessageBox.question(self, 'Revocar confianza',
            '¿Eliminar TODOS los equipos emparejados de este ordenador?\n\n' + names +
            '\n\nPara revocación completa, olvida también este ordenador en los demás equipos.')
        if response == QMessageBox.StandardButton.Yes:
            for key in list(self.trust.peers):
                self.trust.remove(key)
            self.update_status('Equipos olvidados. La próxima conexión requerirá verificar el código.')

    def closeEvent(self, event):
        if not self.quitting and self.tray.isVisible():
            self.hide()
            event.ignore()
            return
        event.accept()


def main():
    app = QApplication(sys.argv)
    try:
        window = MainWindow()
    except Exception as exc:
        QMessageBox.critical(None, 'Error al iniciar', f'{type(exc).__name__}: {exc}')
        return 1
    app.setQuitOnLastWindowClosed(False)
    if '--background' not in sys.argv:
        window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
