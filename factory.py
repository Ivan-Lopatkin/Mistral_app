import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from parsers.base import LandingPageParser
from parsers.tg_channel import TelegramWebParser, TelegramPostParser
from parsers.tg_bot import TelegramBotWebParser

def is_telegram_channel(url: str) -> bool:
    """
    Определяет, ведёт ли ссылка на t.me/{name} на канал (а не на бота).
    Работает и для ссылок вида /s/, и для "чистых" t.me/{name}.
    """
    parsed = urlparse(url)
    if parsed.netloc.lower() not in ("t.me", "telegram.me"):
        return False

    name = parsed.path.lstrip("/")
    # если уже /s/… — проверяем сразу это:
    if name.startswith("s/"):
        test_urls = [url]
    else:
        # сначала пробуем /s/{name}, потом сам {name}
        test_urls = [
            f"{parsed.scheme}://{parsed.netloc}/s/{name}",
            url
        ]

    for u in test_urls:
        try:
            resp = requests.get(u, timeout=5)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            # 1) канал в режиме /s/:
            if soup.select_one(".tgme_channel_info_header"):
                return True
            # 2) «чистый» канал-preview:
            if soup.select_one(f'.tgme_page_context_link[href^="/s/{name}"]'):
                return True
        except requests.RequestException:
            continue

    return False

def get_parser(url: str):
    """
    Возвращает парсер в зависимости от типа ссылки:
      - настоящий канал Telegram → TelegramWebParser
      - бот Telegram               → TelegramBotWebParser
      - всё прочее                 → LandingPageParser
    """
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc not in ("t.me", "telegram.me"):
        return LandingPageParser(url)

    path = parsed.path.lstrip("/")
    
    if re.match(r"^(?:s/)?[^/]+/\d+$", path):
        return TelegramPostParser(url)
    
    if is_telegram_channel(url):
        if not path.startswith("s/"):
            name = path
            url = f"{parsed.scheme}://{parsed.netloc}/s/{name}"
        return TelegramWebParser(url)

    return TelegramBotWebParser(url)
