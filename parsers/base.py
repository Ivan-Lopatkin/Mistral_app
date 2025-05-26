import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional
import logging
import getpass
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LandingPageParser:
    """
    Класс для парсинга посадочной страницы, на которой размещена рекламируемая информация.

    Извлекает базовые элементы:
      - Заголовок страницы (<title>)
      - Мета-описание (<meta name="description">)
      - Мета-ключевые слова (<meta name="keywords">)
      - Заголовки (теги h1-h6)
      - Основной текст страницы (все текстовые блоки)
      
    Эти данные могут служить отправной точкой для последующего этапа анализа с помощью LLM.
    """
    def __init__(self, url: str, timeout: int = 10) -> None:
        """
        Инициализация парсера с указанным URL и таймаутом запроса.

        :param url: URL посадочной страницы.
        :param timeout: Таймаут HTTP-запроса в секундах (по умолчанию 30).
        """
        self.url: str = url
        self.timeout: int = timeout

    def fetch_page(self) -> Optional[str]:
        """
        Загружает HTML-код страницы по заданному URL.

        :return: HTML-код страницы, либо None, если произошла ошибка запроса.
        """
        headers = {
            "User-Agent": (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }
        
        try:
            response = requests.get(self.url, timeout=self.timeout)
            # response.encoding = 'utf-8'
            response.raise_for_status()
            logger.info(f"Страница успешно загружена: {self.url}")
            return response.text
        except Exception as e:
            logger.error(f"Ошибка при загрузке страницы {self.url}: {e}")
            return None
        
    def parse(self) -> Dict[str, Any]:
        """
        Производит парсинг загруженной страницы и извлекает ключевые аспекты:
          - title: Заголовок страницы.
          - meta_description: Мета-описание.
          - meta_keywords: Мета-ключевые слова.
          - headings: Список заголовков (h1-h6).
          - paragraphs: Список параграфов.
          - full_text: Полный текст страницы.

        :return: Словарь с извлечёнными данными.
        """
        html_content = self.fetch_page()
        if not html_content:
            return {"error": "Не удалось загрузить страницу."}

        soup = BeautifulSoup(html_content, 'html.parser')
        result: Dict[str, Any] = {
            'url': self.url,
            'title': None,
            'meta_description': None,
            'meta_keywords': None,
            'headings': [],
            'paragraphs': [],
            'full_text': None
        }

        if soup.title:
            result['title'] = soup.title.get_text(strip=True)

        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            result['meta_description'] = meta_desc.get('content').strip()

        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            result['meta_keywords'] = meta_keywords.get('content').strip()

        headings: List[str] = []
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            for heading in soup.find_all(tag):
                text = heading.get_text(separator=' ', strip=True)
                if text:
                    headings.append(text)
        result['headings'] = headings

        paragraphs: List[str] = []
        for p in soup.find_all('p'):
            text = p.get_text(separator=' ', strip=True)
            if text:
                paragraphs.append(text)
        result['paragraphs'] = paragraphs

        result['full_text'] = soup.get_text(separator='\n', strip=True)

        logger.info("Парсинг завершён успешно.")
        return result