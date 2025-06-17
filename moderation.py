import json
import logging
from urllib.parse import urlparse
import textwrap
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class CreativeGenerator:
    """
    Генерирует рекламные объявления с итеративной валидацией и самокоррекцией:
      - Заголовок (headline) до 40 символов.
      - Текст объявления (ad_text) до 160 символов.
      - Если URL ведёт в Telegram, headline == key_aspects['brand_name'].
      - Нет обращения на "ты", CAPS LOCK, латиницы, орфографических ошибок.
    """
    MAX_HEADLINE = 40
    MAX_AD_TEXT = 160

    def __init__(self, client, model, url: str):
        self.client = client
        self.model = model
        self.url = url

    def _is_telegram(self) -> bool:
        return "t.me" in urlparse(self.url).netloc

    def _build_prompt(
        self,
        customer_prompt: str,
        judge_out: Dict[str, str],
        style: Optional[str] = None
    ) -> str:
        """
        Формирует системный prompt для генерации креатива или отдельного стиля.
        """
        is_telegram = self._is_telegram() and judge_out.get("brand_name")
        brand = judge_out.get("brand_name", "")
        intro = textwrap.dedent(f"""
            Ты — креативный копирайтер, специализирующийся на создании рекламных текстов.
            Твоя задача - заполнить две сущности: рекламный заголовок и текстовый креатив (не более {self.MAX_AD_TEXT} символов!).

            Есть три стиля рекламных текстов:
            1) Стиль 1: Длинный, формальный (≤{self.MAX_AD_TEXT} симв.)
            2) Стиль 2: Эмоциональный, продающий (≤{self.MAX_AD_TEXT} симв.)
            3) Стиль 3: Короткий, цепляющий (5-10 слов)
        """).strip()

        if is_telegram:
            headline_instr = f"Поскольку объявление ведёт в Telegram, для всех стилей headline ДОЛЖЕН БЫТЬ '{brand}'."
        else:
            headline_instr = textwrap.dedent(f"""
                Для каждого стиля сгенерируй:
                  - headline (≤{self.MAX_HEADLINE} симв.)
                  - ad_text (≤{self.MAX_AD_TEXT} симв.)
            """).strip()

        rules = textwrap.dedent(f"""
            Редакционные требования:
              - Обращение только на 'вы'.
              - Без CAPS LOCK и латиницы (если не бренд).
              - headline: ≤{self.MAX_HEADLINE} символов; ad_text: ≤{self.MAX_AD_TEXT} символов.
              
            Промпт от клиента:
            {customer_prompt}
        """).strip()

        if style is None:
            output_tpl = textwrap.dedent("""
                Верни JSON с ключами 'Стиль 1', 'Стиль 2', 'Стиль 3',
                где каждый объект имеет поля 'headline' и 'ad_text'.
            """).strip()
        else:
            output_tpl = f"Верни JSON с одним ключом '{style}' и полями 'headline'/'ad_text'."

        return '\n\n'.join([intro, headline_instr, rules, output_tpl])

    def _validate(self, headline: str, ad_text: str) -> List[str]:
        """
        Проверяет заголовок и текст по правилам, возвращает список ошибок.
        """
        errs: List[str] = []
        if len(headline) > self.MAX_HEADLINE:
            errs.append(f"headline > {self.MAX_HEADLINE}: {len(headline)}")
        if len(ad_text) > self.MAX_AD_TEXT:
            errs.append(f"ad_text > {self.MAX_AD_TEXT}: {len(ad_text)}")
        if ' ты ' in (headline + ' ' + ad_text).lower():
            errs.append("contains 'ты'; use 'вы'")
        if any(ch.isupper() for ch in ad_text) and ad_text != ad_text.title():
            errs.append("contains CAPS LOCK or improper uppercase")
        # if any('a' <= ch.lower() <= 'z' for ch in (headline + ad_text)):
        #     errs.append("contains Latin letters")
        return errs

    def _self_correct(
        self,
        style: str,
        headline: str,
        ad_text: str,
        customer_prompt: str,
        judge_out: Dict[str, str],
        errors: List[str]
    ) -> Dict[str, str]:
        """
        Исправляет креатив через LLM на основе списка ошибок.
        """
        corr_prompt = textwrap.dedent(f"""
            Задача: Исправь рекламный креатив, чтобы:
            - headline не превышал {self.MAX_HEADLINE} символов,
            - ad_text не превышал {self.MAX_AD_TEXT} символов,
            - не содержал обращений на 'ты', CAPS LOCK, латиницы.
            Обнаруженные ошибки: {errors}

            Текущий вариант (стиль {style}):
            headline: "{headline}"
            ad_text: "{ad_text}"

            Верни только JSON {{"{style}": {{"headline": "...", "ad_text": "..."}}}}.
        """)
        messages = [{"role": "system", "content": corr_prompt}]
        try:
            resp = self.client.chat.complete(
                model=self.model,
                messages=messages,
                temperature=0.0,
                top_p=1.0,
                stream=False
            )
            raw = resp.choices[0].message.content.strip('```json').strip('```').strip()
            data = json.loads(raw)
            return data.get(style, {"headline": headline, "ad_text": ad_text})
        except Exception as e:
            logger.error(f"Self-correction error for {style}: {e}")
            return {"headline": headline, "ad_text": ad_text}

    def generate_creatives(self, customer_prompt: str, judge_out: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        """
        Генерирует все стили сразу с последующей валидацией и самокоррекцией.
        """
        resp = self.client.chat.complete(
            model=self.model,
            messages=[{"role": "system", "content": self._build_prompt(customer_prompt, judge_out)}],
            temperature=0.8,
            top_p=0.9,
            stream=False
        )
        content = resp.choices[0].message.content.strip('```json').strip('```').strip()
        creatives = json.loads(content)

        if self._is_telegram():
            brand = judge_out.get('brand_name', '')
            for s in creatives:
                creatives[s]['headline'] = brand

        for style, blk in list(creatives.items()):
            errors = self._validate(blk.get('headline', ''), blk.get('ad_text', ''))
            if errors:
                corrected = self._self_correct(
                    style, blk['headline'], blk['ad_text'], customer_prompt, judge_out, errors
                )
                creatives[style] = corrected
        return creatives

    def generate_style(
        self,
        customer_prompt: str,
        judge_out: Dict[str, str],
        style: str
    ) -> Dict[str, str]:
        """
        Перегенерировать и самокорректировать один выбранный стиль.
        """
        resp = self.client.chat.complete(
            model=self.model,
            messages=[{"role": "system", "content": self._build_prompt(customer_prompt, judge_out, style)}],
            temperature=0.8,
            top_p=0.9,
            stream=False
        )
        raw = resp.choices[0].message.content.strip('```json').strip('```').strip()
        data = json.loads(raw)
        blk = data.get(style, {"headline": "", "ad_text": ""})

        if self._is_telegram():
            blk['headline'] = judge_out.get('brand_name', '')

        errors = self._validate(blk['headline'], blk['ad_text'])
        if errors:
            blk = self._self_correct(
                style, blk['headline'], blk['ad_text'], customer_prompt, judge_out, errors
            )
        return blk