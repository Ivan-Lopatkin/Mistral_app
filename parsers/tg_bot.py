# from urlib.parse import urlparse
from bs4 import BeautifulSoup
from .base import LandingPageParser

class TelegramBotWebParser(LandingPageParser):
    """
    Извлекает из web‑версии Telegram‑бота (https://t.me/<botname>) только:
      - title   — название бота
      - description — описание бота
    """
    def parse(self):
        html = self.fetch_page()
        if not html:
            return {"error": "Не удалось загрузить страницу бота."}

        soup = BeautifulSoup(html, "html.parser")

        title_el = soup.select_one("div.tgme_page_title span")
        title = title_el.get_text(strip=True) if title_el else ""

        desc_el = soup.select_one("div.tgme_page_description")
        description = desc_el.get_text(" ", strip=True) if desc_el else ""

        # channel = urlparse(self.url).path.strip("/")

        return {
            # "bot": channel,
            "title": title,
            "description": description
        }