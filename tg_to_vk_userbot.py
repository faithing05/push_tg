import os

import requests
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.tl import types
from dotenv import load_dotenv

try:
    import qrcode
except ImportError:
    qrcode = None


load_dotenv()


# Данные берутся из переменных окружения, чтобы не хранить секреты в коде.
# Пример значений смотрите в файле .env.example
API_ID = os.getenv("TG_API_ID")
API_HASH = os.getenv("TG_API_HASH")
VK_TOKEN = os.getenv("VK_TOKEN")
VK_USER_ID = os.getenv("VK_USER_ID")
AUTH_MODE = os.getenv("TG_AUTH_MODE", "phone").strip().lower()
DEBUG_LOG = os.getenv("DEBUG_LOG", "1").strip() == "1"

# Имя файла сессии Telethon
SESSION_NAME = "tg_userbot_session"

# Параметры подключения к Telegram
CONNECT_TIMEOUT = 30
CONNECTION_RETRIES = 10
RETRY_DELAY = 5

# Если нужен SOCKS5-прокси, задайте переменные окружения.
PROXY_HOST = os.getenv("PROXY_HOST")
PROXY_PORT = os.getenv("PROXY_PORT")
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")

VK_API_URL = "https://api.vk.com/method/messages.send"
VK_API_VERSION = "5.131"

MEDIA_TYPE_LABELS = (
    (types.MessageMediaGeoLive, "геопозиция"),
    (types.MessageMediaVenue, "место"),
    (types.MessageMediaContact, "контакт"),
    (types.MessageMediaPoll, "опрос"),
    (types.MessageMediaDice, "кубик"),
    (types.MessageMediaGame, "игра"),
    (types.MessageMediaInvoice, "счет"),
    (types.MessageMediaWebPage, "ссылка"),
    (types.MessageMediaUnsupported, "вложение"),
)

ACTION_TYPE_LABELS = (
    (types.MessageActionPhoneCall, "звонок"),
    (types.MessageActionPinMessage, "закрепленное сообщение"),
    (types.MessageActionChatAddUser, "приглашение в чат"),
    (types.MessageActionChatJoinedByLink, "вход по ссылке"),
    (types.MessageActionChatCreate, "создание чата"),
    (types.MessageActionChatDeletePhoto, "удаление фото чата"),
    (types.MessageActionChatDeleteUser, "выход из чата"),
    (types.MessageActionChatEditPhoto, "обновление фото чата"),
    (types.MessageActionChatEditTitle, "изменение названия чата"),
    (types.MessageActionHistoryClear, "очистка истории"),
    (types.MessageActionGameScore, "результат игры"),
    (types.MessageActionPaymentSent, "оплата"),
    (types.MessageActionPaymentSentMe, "платеж"),
    (types.MessageActionScreenshotTaken, "скриншот"),
    (types.MessageActionSecureValuesSent, "отправка данных"),
    (types.MessageActionSecureValuesSentMe, "получение данных"),
    (types.MessageActionContactSignUp, "регистрация в Telegram"),
    (types.MessageActionGeoProximityReached, "геоприближение"),
    (types.MessageActionGroupCall, "групповой звонок"),
    (types.MessageActionInviteToGroupCall, "приглашение в звонок"),
    (types.MessageActionSetMessagesTTL, "таймер удаления сообщений"),
    (types.MessageActionTopicCreate, "создание темы"),
    (types.MessageActionTopicEdit, "изменение темы"),
    (types.MessageActionSuggestProfilePhoto, "предложение фото профиля"),
    (types.MessageActionRequestedPeer, "запрос контакта"),
    (types.MessageActionBotAllowed, "запуск бота"),
    (types.MessageActionWebViewDataSent, "данные из web app"),
    (types.MessageActionWebViewDataSentMe, "данные в web app"),
)


def validate_config() -> bool:
    """Проверяет, что обязательные настройки заданы."""
    missing_vars = []

    if not API_ID:
        missing_vars.append("TG_API_ID")
    if not API_HASH:
        missing_vars.append("TG_API_HASH")
    if not VK_TOKEN:
        missing_vars.append("VK_TOKEN")
    if not VK_USER_ID:
        missing_vars.append("VK_USER_ID")

    if missing_vars:
        print("Не заданы обязательные переменные окружения:")
        for var_name in missing_vars:
            print(f"- {var_name}")
        print("Заполните их перед запуском. Пример есть в файле .env.example.")
        return False

    try:
        int(API_ID)
    except ValueError:
        print("Переменная TG_API_ID должна быть целым числом.")
        return False

    if PROXY_PORT:
        try:
            int(PROXY_PORT)
        except ValueError:
            print("Переменная PROXY_PORT должна быть целым числом.")
            return False

    if AUTH_MODE not in {"phone", "qr"}:
        print("Переменная TG_AUTH_MODE должна быть 'phone' или 'qr'.")
        return False

    return True


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
            int(PROXY_PORT),
            True,
            PROXY_USERNAME,
            PROXY_PASSWORD,
        )

    return TelegramClient(SESSION_NAME, int(API_ID), API_HASH, **client_kwargs)


def build_contact_name(user) -> str:
    """Собирает имя контакта для текста уведомления."""
    first_name = (user.first_name or "").strip()
    last_name = (user.last_name or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    return full_name or "Без имени"


def log_debug(message: str) -> None:
    """Печатает отладочные сообщения, если включен DEBUG_LOG."""
    if DEBUG_LOG:
        print(f"[DEBUG] {message}")


def build_message_content(message) -> str:
    """Возвращает текст сообщения или краткое название вложения."""
    text = (message.raw_text or "").strip()
    if text:
        return text

    if getattr(message, "photo", None):
        return "фото"
    if getattr(message, "video_note", None):
        return "кружочек"
    if getattr(message, "video", None):
        return "видео"
    if getattr(message, "voice", None):
        return "голосовое сообщение"
    if getattr(message, "audio", None):
        return "аудио"
    if getattr(message, "sticker", None):
        return "стикер"
    if getattr(message, "gif", None):
        return "gif"
    if getattr(message, "contact", None):
        return "контакт"
    if getattr(message, "geo", None):
        return "геопозиция"
    if getattr(message, "venue", None):
        return "место"
    if getattr(message, "poll", None):
        return "опрос"
    if getattr(message, "dice", None):
        return "кубик"
    if getattr(message, "game", None):
        return "игра"
    if getattr(message, "invoice", None):
        return "счет"
    if getattr(message, "document", None):
        return "документ"

    media = getattr(message, "media", None)
    for media_type, label in MEDIA_TYPE_LABELS:
        if isinstance(media, media_type):
            return label

    action = getattr(message, "action", None)
    for action_type, label in ACTION_TYPE_LABELS:
        if isinstance(action, action_type):
            return label
    if action is not None:
        return "служебное сообщение"

    return "[Сообщение без текста]"


def send_vk_notification(contact_name: str, message_content: str, quote_message: bool) -> None:
    """Отправляет уведомление в личные сообщения VK."""
    if quote_message:
        message_text = f'{contact_name}\n"{message_content}"'
    else:
        message_text = f'{contact_name}\n{message_content}'
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


async def handle_new_private_message(event) -> None:
    """Обрабатывает входящие личные сообщения."""
    log_debug(
        "Получено новое сообщение: "
        f"private={event.is_private}, out={event.out}, sender_id={event.sender_id}"
    )

    if event.out:
        log_debug("Сообщение пропущено: это исходящее сообщение")
        return

    if not event.is_private:
        log_debug("Сообщение пропущено: это не личный диалог")
        return

    sender = await event.get_sender()
    if sender is None:
        log_debug("Не удалось получить отправителя сообщения")
        return

    contact_name = build_contact_name(sender)
    is_contact = getattr(sender, "contact", False)
    is_mutual_contact = getattr(sender, "mutual_contact", False)
    log_debug(
        "Отправитель: "
        f"{contact_name}, contact={is_contact}, mutual_contact={is_mutual_contact}, "
        f"username={getattr(sender, 'username', None)}"
    )

    # Отправляем уведомление только для контактов или взаимных контактов.
    if not (is_contact or is_mutual_contact):
        log_debug("Сообщение пропущено: отправитель не является контактом Telegram")
        return

    message_content = build_message_content(event.message)
    quote_message = not bool((event.message.raw_text or "").strip())
    log_debug(f"Отправитель прошел фильтр контактов: {contact_name}")
    send_vk_notification(contact_name, message_content, quote_message)


def authorize_with_phone() -> None:
    """Стандартная авторизация по номеру телефона и коду Telegram."""
    client.start()


async def authorize_with_qr() -> None:
    """Авторизация через QR, если аккаунт уже открыт в Telegram на другом устройстве."""
    await client.connect()

    if await client.is_user_authorized():
        return

    qr_login = await client.qr_login()
    print("Откройте Telegram на телефоне: Настройки -> Устройства -> Подключить устройство.")
    if qrcode is not None:
        print("Отсканируйте QR-код ниже:")
        qr = qrcode.QRCode(border=1)
        qr.add_data(qr_login.url)
        qr.print_ascii(invert=True)
    else:
        print("Пакет qrcode не установлен, поэтому выводится ссылка для генерации QR:")
        print(qr_login.url)
        print("Для показа QR прямо в консоли установите: pip install qrcode")

    try:
        await qr_login.wait()
    except SessionPasswordNeededError:
        password = input("Введите пароль двухэтапной аутентификации Telegram: ")
        await client.sign_in(password=password)


def main() -> None:
    """Запускает userbot и начинает слушать новые сообщения."""
    global client

    if not validate_config():
        return

    client = build_telegram_client()
    client.add_event_handler(handle_new_private_message, events.NewMessage())
    print("Запуск Telegram userbot...")
    if AUTH_MODE == "qr":
        print("Выбран вход через QR без SMS.")
    else:
        print("При первом запуске Telethon запросит номер телефона и код подтверждения.")
    if PROXY_HOST and PROXY_PORT:
        print(f"Используется SOCKS5-прокси: {PROXY_HOST}:{PROXY_PORT}")

    try:
        if AUTH_MODE == "qr":
            client.loop.run_until_complete(authorize_with_qr())
        else:
            authorize_with_phone()
    except TimeoutError:
        print("Не удалось подключиться к серверам Telegram: превышено время ожидания.")
        print("Проверьте интернет, VPN/прокси, фаервол или попробуйте другую сеть.")
        return
    except OSError as error:
        print(f"Сетевая ошибка при подключении к Telegram: {error}")
        print("Если Telegram в вашей сети недоступен, попробуйте задать SOCKS5-прокси через переменные окружения.")
        return
    except Exception as error:
        print(f"Ошибка запуска Telegram client: {error}")
        return

    me = client.loop.run_until_complete(client.get_me())
    log_debug(
        f"Авторизован как id={me.id}, username={me.username}, phone={getattr(me, 'phone', None)}"
    )

    print("Userbot запущен. Ожидание новых личных сообщений...")
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
