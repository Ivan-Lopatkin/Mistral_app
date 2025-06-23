import re
import json
import logging
from typing import Any, Dict, List
from urllib.parse import urlparse

from pydantic import BaseModel, ValidationError

# from mistral_common.tokens.tokenizers.mistral import MistralTokenizer
# from mistral_common.protocol.instruct.messages import SystemMessage, UserMessage
# from mistral_common.protocol.instruct.request import ChatCompletionRequest

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class KeyAspectsModel(BaseModel):
    brand_name: str
    themes: List[str]
    prompt: str
    
class JSONParseError(Exception):
    pass

class TimeoutException(Exception):
    """Исключение, выбрасываемое при превышении времени ожидания ответа от API."""
    pass


def timeout_handler(signum, frame):
    """Обработчик сигнала таймаута, выбрасывающий TimeoutException."""
    raise TimeoutException


class LLMAsJudge:
    MAX_RETRIES = 3
    RETRY_DELAY = 1
    
    def __init__(self, client: Any, model: str, url: str, max_retries: int = 3) -> None:
        """
        :param client: Экземпляр клиента для доступа к API Mistral.
        :param model: Имя используемой модели (например, 'mistral-large-latest').
        """
        self.client = client
        self.model = model
        self.url = url
        self.max_retries = max_retries or self.MAX_RETRIES
        
        # self.tokenizer = MistralTokenizer.v3() 
        
    # def _count_messages_tokens(self, system_prompt: str, user_message: str) -> int:
    #     """
    #     Считает токены сразу по всей паре сообщений (system + user).
    #     Возвращает len(tokens) из encode_chat_completion.
    #     """
    #     req = ChatCompletionRequest(
    #         model=self.model,
    #         messages=[
    #             SystemMessage(content=system_prompt),
    #             UserMessage(content=user_message),
    #         ],
    #     )
    #     tokenized = self.tokenizer.encode_chat_completion(req)
    #     return len(tokenized.tokens)
    
    def _is_telegram(self) -> bool:
        return "t.me" in urlparse(self.url).netloc
    
    def _extract_json(self, text: str) -> str:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise JSONParseError("JSON block not found in response")
        return match.group(0)
    
    def _api_call(self, messages: List[Dict[str, str]], temperature: float, top_p: float) -> str:
        retries = 0
        while True:
            try:
                resp = self.client.chat.complete(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    stream=False
                )
                return resp.choices[0].message.content
            except Exception as e:
                err = str(e)
                if '429' in err and retries < self.max_retries:
                    wait = self.RETRY_DELAY * (2 ** retries)
                    logger.warning(f"Получен 429, повтор через {wait}s (попытка {retries+1})...")
                    time.sleep(wait)
                    retries += 1
                    continue
                logger.error(f"API call failed: {e}")
                raise

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
            2. Подобрать исключительно подходящие тематики к посадочной странице ТОЛЬКО из этого списка:
               Бизнес и стартапы; Букмекерство; Видео и фильмы; Даркнет; Дизайн; Для взрослых; Еда и кулинария; Здоровье и Фитнес; Игры;
               Интерьер и строительство; Искусство; Картинки и фото; Карьера; Книги; Криптовалюты; Курсы и гайды; Лингвистика; Маркетинг, PR, реклама; Медицина; Мода и красота; Музыка; Новости и СМИ; Образование; Познавательное; Политика; Право; Природа; Продажи; Психология; Путешествия; Религия; Рукоделие; Семья и дети; Софт и приложения; Спорт; Технологии; Транспорт; Эзотерика; Экономика; Эротика; Юмор и развлечения.
            3. Сгенерировать наилучший промпт для написания рекламных креативов, который описывает исключительно важнейшую информацию и ключевые преимущества с посадочной страницы (не сильно длинный, до 200 символов)

            Верни строго JSON по схеме без лишних объяснений:
            ```json
            {
              "brand_name": "…Название рекламного продукта или услуги…",
              "themes": [
                "..релевантная тематика из списка..", 
                // еще несколько тематик (если релевантные)
              ],
              "prompt": "…Сгенерированный промпт…"
            }'''
        )

        user_message = (
            "Контент посадочной страницы:\n" +
            json.dumps(parsed_data, ensure_ascii=False, indent=2)
        )
        if len(user_message) > 9000:
            user_message = user_message[:9000]   
        #used = self._count_messages_tokens(system_prompt, user_message)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        last_error = None
        response_content = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                response_content = self._api_call(
                    messages=messages,
                    temperature=0.0,
                    top_p=1.0
                )
                # chat_response = self.client.chat.complete(model=self.model, messages=messages, temperature=0)
                # response_content = response_content.choices[0].message.content
                json_block = self._extract_json(response_content)
                obj = KeyAspectsModel.parse_raw(json_block)
                result = obj.dict()
                logger.info("Успешно получили и валидаировали JSON от LLM.")
                if self._is_telegram():
                    result['brand_name'] = str(parsed_data.get('title',''))[:40]
                return result
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                last_error = e
                logger.warning(f"Валидация JSON не прошла: {e}")
                messages.append({
                    "role": "user",
                    "content": (
                        "Ваш предыдущий ответ не прошёл валидацию. "
                        "Вот он:\n\n"
                        f"{response_content}\n\n"
                        "Пожалуйста, исправьте его и верните только чистый JSON "
                        "с полями:\n"
                        "- brand_name: строка\n"
                        "- themes: список строк\n"
                        "- prompt: строка\n"
                    )
                })

        logger.error(f"Не удалось получить корректный JSON: {last_error}")
        raise RuntimeError(f"Failed to extract valid JSON after {self.max_retries} attempts.")