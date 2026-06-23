import requests
from telethon import TelegramClient, events


# Данные Telegram API: получите на https://my.telegram.org
API_ID = 12345678
API_HASH = "your_telegram_api_hash"

# Токен сообщества VK с правом на messages и ID получателя уведомлений
VK_TOKEN = "your_vk_group_token"
VK_USER_ID = 123456789

# Имя файла сессии Telethon
SESSION_NAME = "tg_userbot_session"

# Параметры подключения к Telegram
CONNECT_TIMEOUT = 30
CONNECTION_RETRIES = 10
RETRY_DELAY = 5

# Если нужен SOCKS5-прокси, заполните значения ниже.
# Пример: PROXY_HOST = "127.0.0.1", PROXY_PORT = 1080
PROXY_HOST = None
PROXY_PORT = None
PROXY_USERNAME = None
PROXY_PASSWORD = None

VK_API_URL = "https://api.vk.com/method/messages.send"
VK_API_VERSION = "5.131"


def build_telegram_client() -> TelegramClient:
    """Создает клиент Telegram с настройками подключения."""
    client_kwargs = {
        "timeout": CONNECT_TIMEOUT,
        "connection_retries": CONNECTION_RETRIES,
        "retry_delay": RETRY_DELAY,
        "auto_reconnect": True,
    }

    if PROXY_HOST and PROXY_PORT:
        # Telethon ожидает кортеж параметров SOCKS5-прокси.
        client_kwargs["proxy"] = (
            "socks5",
            PROXY_HOST,
            PROXY_PORT,
            True,
            PROXY_USERNAME,
            PROXY_PASSWORD,
        )

    return TelegramClient(SESSION_NAME, API_ID, API_HASH, **client_kwargs)


def build_contact_name(user) -> str:
    """Собирает имя контакта для текста уведомления."""
    first_name = (user.first_name or "").strip()
    last_name = (user.last_name or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    return full_name or "Без имени"


def send_vk_notification(contact_name: str) -> None:
    """Отправляет уведомление в личные сообщения VK."""
    message_text = f"Получено новое сообщение в Telegram от контакта: {contact_name}"
    payload = {
        "access_token": VK_TOKEN,
        "v": VK_API_VERSION,
        "user_id": VK_USER_ID,
        "random_id": 0,
        "message": message_text,
    }

    try:
        response = requests.post(VK_API_URL, data=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as error:
        print(f"Ошибка сети при отправке уведомления в VK: {error}")
        return
    except ValueError as error:
        print(f"Не удалось разобрать ответ VK API: {error}")
        return

    if "error" in data:
        print(f"VK API вернул ошибку: {data['error']}")
        return

    print(f"Уведомление в VK отправлено для контакта: {contact_name}")


client = build_telegram_client()


@client.on(events.NewMessage(incoming=True))
async def handle_new_private_message(event) -> None:
    """Обрабатывает входящие личные сообщения."""
    if not event.is_private:
        return

    sender = await event.get_sender()
    if sender is None:
        return

    # Отправляем уведомление только для контактов или взаимных контактов.
    if not (getattr(sender, "contact", False) or getattr(sender, "mutual_contact", False)):
        return

    contact_name = build_contact_name(sender)
    send_vk_notification(contact_name)


def main() -> None:
    """Запускает userbot и начинает слушать новые сообщения."""
    print("Запуск Telegram userbot...")
    print("При первом запуске Telethon запросит номер телефона и код подтверждения.")
    if PROXY_HOST and PROXY_PORT:
        print(f"Используется SOCKS5-прокси: {PROXY_HOST}:{PROXY_PORT}")

    try:
        client.start()
    except TimeoutError:
        print("Не удалось подключиться к серверам Telegram: превышено время ожидания.")
        print("Проверьте интернет, VPN/прокси, фаервол или попробуйте другую сеть.")
        return
    except OSError as error:
        print(f"Сетевая ошибка при подключении к Telegram: {error}")
        print("Если Telegram в вашей сети недоступен, попробуйте указать SOCKS5-прокси в начале файла.")
        return
    except Exception as error:
        print(f"Ошибка запуска Telegram client: {error}")
        return

    print("Userbot запущен. Ожидание новых личных сообщений...")
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
