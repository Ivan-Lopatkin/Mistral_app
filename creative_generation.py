import json
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class CreativeGenerator:
    """
    Генерирует рекламные объявления (headline + ad_text) с учётом всех заданных ограничений:
      - Заголовок (headline) до 40 символов.
      - Текст объявления (ad_text) до 160 символов.
      - Если URL ведёт в Telegram (t.me), то заголовок == key_aspects['название'].
      - Все редакционные правила (никаких «ты», не CAPS LOCK, не слишком много эмодзи, и т.д.).
    """
    def __init__(self, client, model, url):
        self.client = client
        self.model = model
        self.url = url

#     def _is_telegram(self):
#         return "t.me" in urlparse(self.url).netloc

    def _build_prompt(self, customer_prompt):
#         if self._is_telegram() and key_aspects.get("название"):
#             headline_instruction = (
#                 f"Поскольку объявление ведёт в Telegram, **не придумывай** новые заголовки. "
#                 f"Для всех трёх стилей headline **должен быть** СТРОГО «{key_aspects['название']}»."
#                 "Далее, используя данные о лендинге, сформируй три варианта рекламного текста, исходя из стилей"
#             )
#         else:
        headline_instruction = (
            "Теперь для каждого стиля сразу сгенерируй два поля:\n"
            "- headline\n"
            "- ad_text\n\n"
            "Для каждого из трёх стилей придумай свой уникальный заголовок и рекламный текст, используя промпт от клиента."
        )

        rules = """
        Редакционные требования:
        - Нельзя обращаться на «ты»; только «вы», повелительное наклонение на «вы».
        - Не использовать CAPS LOCK, лишние аббревиатуры, латиницу (если не бренд).
        - Эмодзи и «!» минимально, без негативной или вульгарной стилистики.
        - Заголовок: до 40 символов. Текст объявления: до 160 символов (пробелы считаются).
        
        Промпт от клиента об объекте рекламы:
        """ + customer_prompt + "\n\n"
        
        prompt = (
            "Ты — креативный копирайтер, специализирующийся на создании рекламных текстов."
            "Твоя задача - заполнить две сущности: рекламный заголовок и текстовый креатив (не более 160 символов!).\n\n"
            "Есть три стиля рекламных текстов:\n"
            "1) Стиль 1: Длинный, формальный, содежржит самые важные преимущества продукта (не более 160 символов!)\n"
            "2) Стиль 2: Эмоциональный, аппелирующий к потенциальным болям клиента, может также быть юмористическим (не более 160 символов!)\n"
            "3) Стиль 3: Самый короткий текст, но цепляющий(не более 5-10 слов)\n\n"
            f"{headline_instruction}\n\n"
            f"{rules}\n"
            # "Ниже приведены only ad_text few-shot примеры для трёх стилей:\n"
            # f"{few_shot_examples}\n\n"
            "Верни результат строго в формате JSON с тремя ключами "
            '"Стиль 1", "Стиль 2", "Стиль 3", '
            "где каждый — объект вида:\n\n"
            "```json\n"
            "{\n"
            '  "Стиль 1": { "headline": "...", "ad_text": "..." },\n'
            '  "Стиль 2": { "headline": "...", "ad_text": "..." },\n'
            '  "Стиль 3": { "headline": "...", "ad_text": "..." }\n'
            "}\n"
            "```"
        )
        print(prompt)
        return prompt

    def generate_creatives(self, key_aspects):
        prompt = self._build_prompt(key_aspects)
        messages = [{"role": "system", "content": prompt}]

        try:
            chat_response = self.client.chat.complete(
                model=self.model,
                messages=messages,
                temperature=0.8,
                top_p=0.9,
                safe_prompt=False,
                stream=False
            )
            content = chat_response.choices[0].message.content.strip()

            if content.startswith("```"):
                content = content.strip("```json").strip("```").strip()
            creatives = json.loads(content)
            logger.info("Креативы успешно получены от LLM.")
        except Exception as e:
            logger.error(f"Ошибка при генерации креативов: {e}")
            creatives = {"headline": "", "ad_text": ""}
        return creatives