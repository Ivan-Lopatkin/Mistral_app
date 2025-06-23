from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from .base import LandingPageParser

class TelegramWebParser(LandingPageParser):
    """
    Парсер публичного Telegram‑канала через веб‑интерфейс t.me/s/<channel>.

    Извлекает:
      - title: название канала
      - description: описание канала
      - last_posts: список последних 5 сообщений, каждый с датой, текстом и ссылкой на оригинал
    """
    def parse(self):
        html = self.fetch_page()
        if not html:
            return {"error": "Не удалось загрузить страницу."}

        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.select_one(".tgme_channel_info_header")
        title = title_tag.get_text(strip=True) if title_tag else ""

        desc_tag = soup.select_one(".tgme_channel_info_description")
        description = desc_tag.get_text(" ", strip=True) if desc_tag else ""

        posts = []
        for msg_div in soup.select(".tgme_widget_message")[-10:]:
            text_tag = msg_div.select_one(".tgme_widget_message_text")
            text = text_tag.get_text("\n", strip=True) if text_tag else ""

            posts.append({
                "text": text
            })

        # channel = urlparse(self.url).path.rstrip("/").split("/")[-1]

        return {
            # "channel": channel,
            "title": title,
            "description": description,
            "last_posts": posts
        }
    
class TelegramPostParser(LandingPageParser):
    def parse(self):
        html = self.fetch_page()
        if not html:
            return {"error": "Не удалось загрузить страницу."}

        soup = BeautifulSoup(html, "html.parser")
        data = {}
        og_title = soup.find("meta", property="og:title")
        data["title"] = og_title["content"] if og_title and og_title.has_attr("content") else None

        og_desc = soup.find("meta", property="og:description")
        data["description"] = og_desc["content"] if og_desc and og_desc.has_attr("content") else None

        # og_img = soup.find("meta", property="og:image")
        # data["image"] = og_img["content"] if og_img and og_img.has_attr("content") else None

        twitter_url = soup.find("meta", attrs={"name": "twitter:app:url:googleplay"})
        data["url"] = twitter_url["content"] if twitter_url and twitter_url.has_attr("content") else None
        return data
