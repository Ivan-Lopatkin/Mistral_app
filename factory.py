import re
from parsers.base import LandingPageParser
from parsers.tg_channel import TelegramWebParser
from parsers.tg_bot import TelegramBotWebParser

def get_parser(url):
    if re.match(r"https?://t\.me/s/", url):
        return TelegramWebParser(url)
    if re.match(r"https?://t\.me/[^/]+/?$", url):
        return TelegramBotWebParser(url)
    return LandingPageParser(url)
