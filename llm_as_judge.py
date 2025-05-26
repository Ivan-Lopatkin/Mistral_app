import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TimeoutException(Exception):
    """Исключение, выбрасываемое при превышении времени ожидания ответа от API."""
    pass


def timeout_handler(signum, frame):
    """Обработчик сигнала таймаута, выбрасывающий TimeoutException."""
    raise TimeoutException


class LLMAsJudge:
    def __init__(self, client: Any, model: str) -> None:
        """
        :param client: Экземпляр клиента для доступа к API Mistral.
        :param model: Имя используемой модели (например, 'mistral-large-latest').
        """
        self.client = client
        self.model = model

    def extract_key_aspects(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        :param parsed_data: Словарь с разобранными данными страницы.
        :return: Словарь с ключевыми аспектами, полученными от LLM.
                 Ключи: 'название', 'категория', 'оффер', 'ключевые_преимущества', 'гео'.
                 В случае ошибки возвращается пустой словарь.
        """

        system_prompt = (
            '''Ты — эксперт по маркетингу и таргетингу. Твоя задача — на основе описания посадочной страницы:
            1. Выделить название рекламного объекта
2. Сгенерировать 3–5 наиболее релевантных категорий продукта или услуги. При выборе опирайся на бизнес-логику: эти категории будут использоваться в алгоритмах для поиска и сегментирования целевой аудитории, где можно прорекламировать этот продукт.
3. Для каждой сгенерированной категории подобрать ровно одну тематику ТОЛЬКО из этого списка:
   Бизнес и стартапы; Букмекерство; Видео и фильмы; Даркнет; Дизайн; Для взрослых; Еда и кулинария; Здоровье и Фитнес; Игры;
   Интерьер и строительство; Искусство; Картинки и фото; Карьера; Книги; Криптовалюты; Курсы и гайды; Лингвистика; Маркетинг, PR, реклама; Медицина; Мода и красота; Музыка; Новости и СМИ; Образование; Познавательное; Политика; Право; Природа; Продажи; Психология; Путешествия; Религия; Рукоделие; Семья и дети; Софт и приложения; Спорт; Технологии; Транспорт; Эзотерика; Экономика; Эротика; Юмор и развлечения.
   
Верни результат в виде JSON без пояснений:
```json
{
  "brend_name": "…Название рекламного продукта или услуги…"
  "categories": [
    {
      "name": "…сгенерированная категория…",
      "theme": "…из списка тем…"
    },
    // ещё 2–4 пары
  ]
}'''
        )

        user_message = (
            "Контент посадочной страницы:\n" +
            json.dumps(parsed_data, ensure_ascii=False, indent=2)
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        print(system_prompt)
        print(user_message)
        try:
            chat_response = self.client.chat.complete(model=self.model, messages=messages)
            response_content = chat_response.choices[0].message.content
            response_content = response_content.strip("```json").strip("```").strip()
            key_aspects = json.loads(response_content)
            logger.info("Ключевые аспекты успешно получены от LLM.")
        except Exception as e:
            logger.error(f"Ошибка при извлечении ключевых аспектов: {e}")
            key_aspects = {}

        return key_aspects