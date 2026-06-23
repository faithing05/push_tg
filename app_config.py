import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class AppConfig:
    tg_api_id: str = ""
    tg_api_hash: str = ""
    vk_token: str = ""
    vk_user_id: str = ""
    delete_vk_on_read: bool = False
    proxy_host: str = ""
    proxy_port: str = ""
    proxy_username: str = ""
    proxy_password: str = ""
    debug_log: bool = True
    session_name: str = "tg_userbot_session"


@dataclass(frozen=True)
class AppPaths:
    app_dir: Path
    config_path: Path
    message_links_path: Path
    logs_dir: Path
    log_path: Path
    session_dir: Path
    legacy_config_path: Path
    legacy_env_path: Path
    legacy_session_dir: Path


def _normalize_string(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def get_app_paths(base_dir: Path) -> AppPaths:
    appdata_root = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    app_dir = appdata_root / "TgVkNotifier"
    return AppPaths(
        app_dir=app_dir,
        config_path=app_dir / "app_config.json",
        message_links_path=app_dir / "message_links.json",
        logs_dir=app_dir / "logs",
        log_path=app_dir / "logs" / "app.log",
        session_dir=app_dir / "session",
        legacy_config_path=base_dir / "app_config.json",
        legacy_env_path=base_dir / ".env",
        legacy_session_dir=base_dir,
    )


def _build_config(data: dict) -> AppConfig:
    return AppConfig(
        tg_api_id=_normalize_string(data.get("tg_api_id")),
        tg_api_hash=_normalize_string(data.get("tg_api_hash")),
        vk_token=_normalize_string(data.get("vk_token")),
        vk_user_id=_normalize_string(data.get("vk_user_id")),
        delete_vk_on_read=bool(data.get("delete_vk_on_read", False)),
        proxy_host=_normalize_string(data.get("proxy_host")),
        proxy_port=_normalize_string(data.get("proxy_port")),
        proxy_username=_normalize_string(data.get("proxy_username")),
        proxy_password=_normalize_string(data.get("proxy_password")),
        debug_log=bool(data.get("debug_log", True)),
        session_name=_normalize_string(data.get("session_name")) or "tg_userbot_session",
    )


def load_config(paths: AppPaths) -> AppConfig:
    config_path = paths.config_path
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}

        return _build_config(data)

    if paths.legacy_config_path.exists():
        try:
            data = json.loads(paths.legacy_config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        return _build_config(data)

    load_dotenv(paths.legacy_env_path)
    return AppConfig(
        tg_api_id=_normalize_string(os.getenv("TG_API_ID")),
        tg_api_hash=_normalize_string(os.getenv("TG_API_HASH")),
        vk_token=_normalize_string(os.getenv("VK_TOKEN")),
        vk_user_id=_normalize_string(os.getenv("VK_USER_ID")),
        delete_vk_on_read=_normalize_string(os.getenv("DELETE_VK_ON_READ", "0")) == "1",
        proxy_host=_normalize_string(os.getenv("PROXY_HOST")),
        proxy_port=_normalize_string(os.getenv("PROXY_PORT")),
        proxy_username=_normalize_string(os.getenv("PROXY_USERNAME")),
        proxy_password=_normalize_string(os.getenv("PROXY_PASSWORD")),
        debug_log=_normalize_string(os.getenv("DEBUG_LOG", "1")) == "1",
        session_name=_normalize_string(os.getenv("SESSION_NAME")) or "tg_userbot_session",
    )


def save_config(paths: AppPaths, config: AppConfig) -> Path:
    paths.app_dir.mkdir(parents=True, exist_ok=True)
    config_path = paths.config_path
    payload = asdict(config)
    config_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return config_path


def get_session_storage_path(paths: AppPaths, session_name: str) -> Path:
    return paths.session_dir / (session_name or "tg_userbot_session")


def migrate_legacy_session_if_needed(paths: AppPaths, session_name: str) -> Path:
    paths.session_dir.mkdir(parents=True, exist_ok=True)
    target = get_session_storage_path(paths, session_name)
    target_session = target.with_suffix(".session")
    target_journal = target.with_suffix(".session-journal")

    if target_session.exists() or target_journal.exists():
        return target

    legacy = paths.legacy_session_dir / (session_name or "tg_userbot_session")
    legacy_session = legacy.with_suffix(".session")
    legacy_journal = legacy.with_suffix(".session-journal")

    if legacy_session.exists():
        target_session.write_bytes(legacy_session.read_bytes())
    if legacy_journal.exists():
        target_journal.write_bytes(legacy_journal.read_bytes())

    return target


def validate_config(config: AppConfig) -> list[str]:
    errors: list[str] = []

    if not config.tg_api_id:
        errors.append("Не заполнено поле TG API ID.")
    if not config.tg_api_hash:
        errors.append("Не заполнено поле TG API Hash.")
    if not config.vk_token:
        errors.append("Не заполнено поле VK Token.")
    if not config.vk_user_id:
        errors.append("Не заполнено поле VK User ID.")

    if config.tg_api_id:
        try:
            int(config.tg_api_id)
        except ValueError:
            errors.append("TG API ID должен быть целым числом.")

    if config.proxy_port:
        try:
            int(config.proxy_port)
        except ValueError:
            errors.append("Proxy Port должен быть целым числом.")

    return errors
