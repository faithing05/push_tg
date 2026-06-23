import io
import logging
import sys
from pathlib import Path

import qrcode
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app_config import AppConfig, get_app_paths, load_config, save_config, validate_config
from bot_core import LOGGER_NAME, TelegramVkNotifierService, setup_logging


APP_TITLE = "Telegram to VK Notifier"
BASE_DIR = Path(__file__).resolve().parent


class LogEmitter(QObject):
    message = pyqtSignal(str)


class QtLogHandler(logging.Handler):
    def __init__(self, emitter: LogEmitter) -> None:
        super().__init__()
        self.emitter = emitter
        self.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        self.emitter.message.emit(self.format(record))


class BotBridge(QObject):
    status_changed = pyqtSignal(str)
    state_changed = pyqtSignal(dict)
    qr_ready = pyqtSignal(str)

    def __init__(self, config: AppConfig, paths) -> None:
        super().__init__()
        self.service = TelegramVkNotifierService(
            config=config,
            paths=paths,
            on_status=self.status_changed.emit,
            on_state=self.state_changed.emit,
            on_qr_url=self.qr_ready.emit,
        )
        self.service.start()

    def update_config(self, config: AppConfig) -> None:
        self.service.update_config(config)

    def refresh_authorization(self) -> None:
        self.service.refresh_authorization()

    def begin_qr_login(self) -> None:
        self.service.begin_qr_login()

    def send_phone_code(self, phone_number: str) -> None:
        self.service.send_phone_code(phone_number)

    def submit_code(self, code: str) -> None:
        self.service.submit_code(code)

    def submit_password(self, password: str) -> None:
        self.service.submit_password(password)

    def start_monitoring(self) -> None:
        self.service.start_monitoring()

    def stop_monitoring(self) -> None:
        self.service.stop_monitoring()

    def shutdown(self) -> None:
        self.service.shutdown()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(980, 760)

        self.paths = get_app_paths(BASE_DIR)
        self.config = load_config(self.paths)
        self.log_path = setup_logging(self.paths, self.config.debug_log)
        self.logger = logging.getLogger(LOGGER_NAME)
        self.log_emitter = LogEmitter()
        self.log_emitter.message.connect(self.append_log)
        self.log_handler = QtLogHandler(self.log_emitter)
        self.logger.addHandler(self.log_handler)

        self.bridge = BotBridge(self.config, self.paths)
        self.bridge.status_changed.connect(self.on_status_changed)
        self.bridge.state_changed.connect(self.on_state_changed)
        self.bridge.qr_ready.connect(self.on_qr_ready)

        self.current_state = {
            "authorized": False,
            "authorized_user": "",
            "running": False,
            "awaiting_code": False,
            "awaiting_password": False,
            "auth_mode": "idle",
        }

        self.tray_icon: QSystemTrayIcon | None = None

        self._build_ui()
        self._create_tray()
        self.load_form_from_config()
        self.logger.info("Desktop-приложение запущено")
        self.bridge.refresh_authorization()

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)

        self.status_label = QLabel("Статус: инициализация...")
        self.status_label.setWordWrap(True)
        root_layout.addWidget(self.status_label)

        tabs = QTabWidget()
        tabs.addTab(self._build_settings_tab(), "Настройки")
        tabs.addTab(self._build_auth_tab(), "Авторизация")
        tabs.addTab(self._build_logs_tab(), "Логи")
        root_layout.addWidget(tabs)

        controls_layout = QHBoxLayout()
        self.save_button = QPushButton("Сохранить настройки")
        self.save_button.clicked.connect(self.save_current_config)
        self.refresh_button = QPushButton("Проверить авторизацию")
        self.refresh_button.clicked.connect(self.bridge.refresh_authorization)
        self.start_button = QPushButton("Старт")
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button = QPushButton("Стоп")
        self.stop_button.clicked.connect(self.bridge.stop_monitoring)
        controls_layout.addWidget(self.save_button)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.stop_button)
        root_layout.addLayout(controls_layout)

        self.setCentralWidget(central)
        self._apply_state()

    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        api_group = QGroupBox("Telegram и VK")
        api_form = QFormLayout(api_group)
        self.tg_api_id_input = QLineEdit()
        self.tg_api_hash_input = QLineEdit()
        self.vk_token_input = QLineEdit()
        self.vk_token_input.setEchoMode(QLineEdit.Password)
        self.vk_user_id_input = QLineEdit()
        self.session_name_input = QLineEdit()
        api_form.addRow("TG API ID", self.tg_api_id_input)
        api_form.addRow("TG API Hash", self.tg_api_hash_input)
        api_form.addRow("VK Token", self.vk_token_input)
        api_form.addRow("VK User ID", self.vk_user_id_input)
        api_form.addRow("Session Name", self.session_name_input)

        proxy_group = QGroupBox("SOCKS5 proxy")
        proxy_form = QFormLayout(proxy_group)
        self.proxy_host_input = QLineEdit()
        self.proxy_port_input = QLineEdit()
        self.proxy_username_input = QLineEdit()
        self.proxy_password_input = QLineEdit()
        self.proxy_password_input.setEchoMode(QLineEdit.Password)
        proxy_form.addRow("Host", self.proxy_host_input)
        proxy_form.addRow("Port", self.proxy_port_input)
        proxy_form.addRow("Username", self.proxy_username_input)
        proxy_form.addRow("Password", self.proxy_password_input)

        misc_group = QGroupBox("Прочее")
        misc_layout = QVBoxLayout(misc_group)
        self.debug_log_checkbox = QCheckBox("Подробные логи")
        self.delete_vk_on_read_checkbox = QCheckBox(
            "Удалять уведомления в VK после прочтения в Telegram"
        )
        misc_layout.addWidget(self.debug_log_checkbox)
        misc_layout.addWidget(self.delete_vk_on_read_checkbox)
        self.config_hint_label = QLabel(
            f"Настройки сохраняются в: {self.paths.config_path}\n"
            f"Лог-файл: {self.log_path}\n"
            f"Сессия Telegram: {self.paths.session_dir}"
        )
        self.config_hint_label.setWordWrap(True)
        misc_layout.addWidget(self.config_hint_label)

        layout.addWidget(api_group)
        layout.addWidget(proxy_group)
        layout.addWidget(misc_group)
        layout.addStretch(1)
        return tab

    def _build_auth_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info_group = QGroupBox("Состояние")
        info_layout = QVBoxLayout(info_group)
        self.auth_status_label = QLabel("Telegram не авторизован")
        self.auth_status_label.setWordWrap(True)
        info_layout.addWidget(self.auth_status_label)

        qr_group = QGroupBox("Вход по QR")
        qr_layout = QVBoxLayout(qr_group)
        self.qr_button = QPushButton("Показать QR")
        self.qr_button.clicked.connect(self.begin_qr_login)
        self.qr_label = QLabel("QR еще не создан")
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setMinimumHeight(320)
        self.qr_label.setStyleSheet("border: 1px solid #999; background: white;")
        qr_layout.addWidget(self.qr_button)
        qr_layout.addWidget(self.qr_label)

        phone_group = QGroupBox("Вход по номеру")
        phone_layout = QGridLayout(phone_group)
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Например: +79991234567")
        self.send_code_button = QPushButton("Получить код")
        self.send_code_button.clicked.connect(self.send_phone_code)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Код из Telegram")
        self.submit_code_button = QPushButton("Подтвердить код")
        self.submit_code_button.clicked.connect(self.submit_code)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Пароль 2FA, если включен")
        self.submit_password_button = QPushButton("Отправить пароль")
        self.submit_password_button.clicked.connect(self.submit_password)
        phone_layout.addWidget(QLabel("Телефон"), 0, 0)
        phone_layout.addWidget(self.phone_input, 0, 1)
        phone_layout.addWidget(self.send_code_button, 0, 2)
        phone_layout.addWidget(QLabel("Код"), 1, 0)
        phone_layout.addWidget(self.code_input, 1, 1)
        phone_layout.addWidget(self.submit_code_button, 1, 2)
        phone_layout.addWidget(QLabel("Пароль 2FA"), 2, 0)
        phone_layout.addWidget(self.password_input, 2, 1)
        phone_layout.addWidget(self.submit_password_button, 2, 2)

        layout.addWidget(info_group)
        layout.addWidget(qr_group)
        layout.addWidget(phone_group)
        layout.addStretch(1)
        return tab

    def _build_logs_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(3000)
        self.log_file_label = QLabel(f"Лог-файл: {self.log_path}")
        self.log_file_label.setWordWrap(True)
        layout.addWidget(self.log_file_label)
        layout.addWidget(self.log_output)
        return tab

    def _create_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.logger.warning("Системный трей недоступен")
            return

        icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.setWindowIcon(icon)
        self.tray_icon = QSystemTrayIcon(icon, self)
        tray_menu = QMenu(self)

        show_action = QAction("Открыть", self)
        show_action.triggered.connect(self.show_normal)
        start_action = QAction("Старт", self)
        start_action.triggered.connect(self.start_monitoring)
        stop_action = QAction("Стоп", self)
        stop_action.triggered.connect(self.bridge.stop_monitoring)
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.exit_application)

        tray_menu.addAction(show_action)
        tray_menu.addAction(start_action)
        tray_menu.addAction(stop_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.setToolTip(APP_TITLE)
        self.tray_icon.show()

    def collect_form_config(self) -> AppConfig:
        return AppConfig(
            tg_api_id=self.tg_api_id_input.text().strip(),
            tg_api_hash=self.tg_api_hash_input.text().strip(),
            vk_token=self.vk_token_input.text().strip(),
            vk_user_id=self.vk_user_id_input.text().strip(),
            delete_vk_on_read=self.delete_vk_on_read_checkbox.isChecked(),
            proxy_host=self.proxy_host_input.text().strip(),
            proxy_port=self.proxy_port_input.text().strip(),
            proxy_username=self.proxy_username_input.text().strip(),
            proxy_password=self.proxy_password_input.text().strip(),
            debug_log=self.debug_log_checkbox.isChecked(),
            session_name=self.session_name_input.text().strip() or "tg_userbot_session",
        )

    def load_form_from_config(self) -> None:
        self.tg_api_id_input.setText(self.config.tg_api_id)
        self.tg_api_hash_input.setText(self.config.tg_api_hash)
        self.vk_token_input.setText(self.config.vk_token)
        self.vk_user_id_input.setText(self.config.vk_user_id)
        self.delete_vk_on_read_checkbox.setChecked(self.config.delete_vk_on_read)
        self.proxy_host_input.setText(self.config.proxy_host)
        self.proxy_port_input.setText(self.config.proxy_port)
        self.proxy_username_input.setText(self.config.proxy_username)
        self.proxy_password_input.setText(self.config.proxy_password)
        self.debug_log_checkbox.setChecked(self.config.debug_log)
        self.session_name_input.setText(self.config.session_name)

    def save_current_config(self) -> bool:
        new_config = self.collect_form_config()
        errors = validate_config(new_config)
        if errors:
            QMessageBox.warning(self, APP_TITLE, "\n".join(errors))
            return False

        config_changed = new_config != self.config

        if config_changed:
            save_config(self.paths, new_config)
            self.config = new_config
            self.bridge.update_config(new_config)
            setup_logging(self.paths, new_config.debug_log)
            self.logger.info("Настройки сохранены")
            self.on_status_changed("Настройки сохранены")

        return True

    def begin_qr_login(self) -> None:
        if self.save_current_config():
            self.bridge.begin_qr_login()

    def send_phone_code(self) -> None:
        if self.save_current_config():
            self.bridge.send_phone_code(self.phone_input.text())

    def submit_code(self) -> None:
        self.bridge.submit_code(self.code_input.text())

    def submit_password(self) -> None:
        self.bridge.submit_password(self.password_input.text())

    def start_monitoring(self) -> None:
        if self.save_current_config():
            self.bridge.start_monitoring()

    def on_status_changed(self, message: str) -> None:
        self.status_label.setText(f"Статус: {message}")
        if self.tray_icon is not None:
            self.tray_icon.setToolTip(f"{APP_TITLE}\n{message}")

    def on_state_changed(self, state: dict) -> None:
        self.current_state.update(state)
        self._apply_state()

    def on_qr_ready(self, url: str) -> None:
        qr = qrcode.QRCode(border=2, box_size=8)
        qr.add_data(url)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue(), "PNG")
        self.qr_label.setPixmap(pixmap.scaled(280, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _apply_state(self) -> None:
        authorized = self.current_state.get("authorized", False)
        running = self.current_state.get("running", False)
        awaiting_code = self.current_state.get("awaiting_code", False)
        awaiting_password = self.current_state.get("awaiting_password", False)
        authorized_user = self.current_state.get("authorized_user", "")

        if authorized:
            self.auth_status_label.setText(f"Telegram авторизован: {authorized_user}")
        else:
            self.auth_status_label.setText("Telegram не авторизован")

        self.start_button.setEnabled(authorized and not running)
        self.stop_button.setEnabled(running)
        self.submit_code_button.setEnabled(awaiting_code)
        self.code_input.setEnabled(awaiting_code)
        self.submit_password_button.setEnabled(awaiting_password)
        self.password_input.setEnabled(awaiting_password)

    def append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def show_normal(self) -> None:
        self.show()
        self.setWindowState(Qt.WindowNoState)
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_normal()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.tray_icon is not None and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                APP_TITLE,
                "Приложение продолжает работать в трее.",
                QSystemTrayIcon.Information,
                2500,
            )
            return

        super().closeEvent(event)

    def exit_application(self) -> None:
        if self.tray_icon is not None:
            self.tray_icon.hide()
        self.bridge.shutdown()
        self.logger.removeHandler(self.log_handler)
        QApplication.instance().quit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
