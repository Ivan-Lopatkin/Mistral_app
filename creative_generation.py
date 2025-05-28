import json
import logging
from urllib.parse import urlparse
import textwrap
from typing import Optional, Dict

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

    def _is_telegram(self):
        return "t.me" in urlparse(self.url).netloc


    def _build_prompt(
        self,
        customer_prompt: str,
        judge_out: Dict[str, str],
        style: Optional[str] = None
    ) -> str:
        """
        Формирует system-prompt для генерации креативов.

        :param customer_prompt: текст, введённый пользователем (описание продукта).
        :param judge_out: вывод LLMAsJudge с полем 'brand_name'.
        :param style: если задано, генерим только один стиль, иначе — сразу все три.
        :return: готовый prompt.
        """
        is_telegram = self._is_telegram() and judge_out.get("brand_name")
        brand = judge_out.get("brand_name", "")
        
        intro = textwrap.dedent(f"""
                Ты — креативный копирайтер, специализирующийся на создании рекламных текстов.
                Твоя задача - заполнить две сущности: рекламный заголовок и текстовый креатив (не более 160 символов!).
                
                Есть три стиля рекламных текстов:
                1) Стиль 1: Длинный, формальный, содежржит самые важные преимущества продукта (не более 160 символов!)
                2) Стиль 2: Эмоциональный, аппелирующий к потенциальным болям клиента, может также быть юмористическим (не более 160 символов!)
                3) Стиль 3: Самый короткий текст, но цепляющий(не более 5-10 слов)
            """).strip()
        # Инструкция по заголовку
        if is_telegram:
            headline_instr = textwrap.dedent(f"""
                Поскольку объявление ведёт в Telegram, не придумывай новые заголовки.
                Для всех стилей headline ДОЛЖЕН БЫТЬ "{brand}".
            """).strip()
        else:
            headline_instr = textwrap.dedent("""
                Для каждого стиля сгенерируй два поля:
                  - headline (до 40 символов)
                  - ad_text (до 160 символов)
                Придумай для каждого стиля свой уникальный заголовок и текст.
            """).strip()

        # Общие правила
        rules = textwrap.dedent(f"""
            Редакционные требования:
            - Обращение только на "вы".
            - Без CAPS LOCK и латиницы (если не бренд).
            - Пунктуация и орфография на высоте.
            - headline: ≤40 символов; ad_text: ≤160 символов.

            Промпт от клиента:
            {customer_prompt}
        """).strip()

        # Шаблон на все стили
        if style is None:
            output_tpl = textwrap.dedent("""
                Верни JSON с тремя ключами: "Стиль 1", "Стиль 2", "Стиль 3",
                где каждый — объект вида:
                ```json
                {
                  "Стиль 1": { "headline": "...", "ad_text": "..." },
                  "Стиль 2": { "headline": "...", "ad_text": "..." },
                  "Стиль 3": { "headline": "...", "ad_text": "..." }
                }
                ```
            """).strip()
        else:
            output_tpl = textwrap.dedent(f"""
                Верни JSON с одним ключом "{style}", где значение —
                объект вида:
                ```json
                {{
                  "{style}": {{ "headline": "...", "ad_text": "..." }}
                }}
                ```
            """).strip()

        blocks = [
            intro,
            headline_instr,
            rules,
            output_tpl
        ]
        prompt = "\n\n".join(blocks)
        logger.debug("Built prompt:\n%s", prompt)
        return prompt

    def generate_creatives(self, customer_prompt, judge_out):
        prompt = self._build_prompt(customer_prompt, judge_out)
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
            
        if self._is_telegram():
            brand_title = judge_out.get("brand_name")
            for style in ["Стиль 1", "Стиль 2", "Стиль 3"]:
                creatives.setdefault(style, {})
                creatives[style]["headline"] = brand_title
        return creatives
    
    def generate_style(self, customer_prompt, judge_out, style) -> Dict[str, str]:
        """
        Перегенерировать только один стиль: style ∈ {"Стиль 1", "Стиль 2", "Стиль 3"}.
        Возвращает {"headline": "...", "ad_text": "..."} для данного стиля.
        """
        prompt = self._build_prompt(customer_prompt, judge_out, style)
        messages = [{"role": "system", "content": prompt}]
        try:
            resp = self.client.chat.complete(
                model=self.model,
                messages=messages,
                temperature=0.8,
                top_p=0.9,
                stream=False
            )
            raw = resp.choices[0].message.content.strip("```json").strip("```").strip()
            data = json.loads(raw)
            block = data.get(style, {"headline": "", "ad_text": ""})
        except Exception as e:
            logger.error(f"Ошибка при регенерации стиля {style}: {e}")
            block = {"headline": "", "ad_text": ""}

        if self._is_telegram():
            brand_title = judge_out.get("brand_name")
            block["headline"] = brand_title
        return block