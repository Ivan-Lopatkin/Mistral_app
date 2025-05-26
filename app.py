import streamlit as st

import json
import logging
import os
import re
from urllib.parse import urlparse

from llm_as_judge import LLMAsJudge
from factory import get_parser
from creative_generation import CreativeGenerator
from mistralai import Mistral

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Ad Creative Playground", layout="centered")
st.title("Ad Creative Playground")

# 1) Инструкция по получению ключа
st.header("1. Как получить API-ключ")
st.markdown("""
1. Зарегистрируйтесь на https://console.mistral.ai/api-keys  
2. Перейдите в раздел **API Keys**.  
3. Скопируйте ключ и сохраните его.
""")

# 2) Ввод ключа
st.header("2. Введите ваш API-ключ")
api_key = st.text_input("API Key", type="password", placeholder="sk-...")

# 3) Выбор модели
st.header("3. Выберите модель")
model_options = [
    "mistral-small-latest",
    "mistral-large-latest",
    "open-mistral-7b"
]
st.session_state.setdefault("selected_model", model_options[0])
st.session_state["selected_model"] = st.selectbox(
    "Модель",
    model_options,
    index=model_options.index(st.session_state["selected_model"])
)

# Клиент Mistral
client = Mistral(api_key=api_key)

# Инициализация стейта
if "parsed_data" not in st.session_state:
    st.session_state["parsed_data"] = None
if "judge_output" not in st.session_state:
    st.session_state["judge_output"] = None
if "user_prompt" not in st.session_state:
    st.session_state["user_prompt"] = None
if "generated_creatives" not in st.session_state:
    st.session_state["generated_creatives"] = None

# 4) Ввод URL и извлечение категорий
st.header("4. Введите URL посадочной страницы")
url_input = st.text_input("URL", placeholder="https://example.com")
if url_input and st.button("Проанализировать страницу"):
    with st.spinner("Парсинг и извлечение категорий…"):
        parser = get_parser(url_input)
        parsed = parser.parse()
        if "error" in parsed:
            st.error(parsed["error"])
        else:
            st.session_state["parsed_data"] = parsed
            llm = LLMAsJudge(client=client, model=st.session_state["selected_model"])
            judge_out = llm.extract_key_aspects(parsed)
            st.session_state["judge_output"] = judge_out

# 5) Показать категории и запросить свой промпт
if st.session_state["judge_output"]:
    out = st.session_state["judge_output"]
    brand_input = st.text_input(
        label="Название",
        value=out.get("brend_name", ""),
        help="При необходимости отредактируйте название"
    )

    category_names = [c["name"] for c in out.get("categories", [])]

    # Отображаем их в виде тегов, которые пользователь может убирать
    selected = st.multiselect(
        label="Чем вы занимаетесь",
        options=category_names,
        default=category_names,
        help="Отметьте релевантные категории (чтобы убрать — нажмите на × в теге)"
    )

    # Сохраняем выбор в сессии, если понадобится дальше
    st.session_state["selected_categories"] = selected

    st.header("5. Опишите рекламируемый объект своими словами")
    user_prompt = st.text_area(
        "Ваш промпт",
        placeholder="Например: «Наш продукт — это… То, чем он полезен…»",
        height=150
    )
    if user_prompt:
        st.session_state["user_prompt"] = user_prompt

# 6) Генерация креативов
if st.session_state["user_prompt"]:
    if st.button("6. Сгенерировать рекламные тексты"):
        with st.spinner("Генерация креативов…"):
            gen = CreativeGenerator(
                client=client,
                model=st.session_state["selected_model"],
                url=url_input
            )
            creat = gen.generate_creatives(st.session_state["user_prompt"])
            st.session_state["generated_creatives"] = creat

# 7) Редактирование и финальный вывод
if st.session_state["generated_creatives"]:
    st.header("7. Проверьте и отредактируйте креативы")
    with st.form("edit_creatives_form"):
        final = {}
        for style in ["Стиль 1","Стиль 2","Стиль 3"]:
            block = st.session_state["generated_creatives"].get(style, {})
            # если телеграм-ресурс — заголовок брендовый
            default_head = (
                st.session_state["parsed_data"].get("title","")
                if "t.me" in url_input else
                block.get("headline","")
            )
            head = st.text_input(f"{style} — Заголовок (≤40):", value=default_head, key=f"{style}_h")
            txt = st.text_area(f"{style} — Текст (≤160):", value=block.get("ad_text",""), key=f"{style}_t", height=100)

            # базовая валидация
            if len(head)>40:
                st.error(f"{style}: Заголовок >40 символов ({len(head)})")
            if len(txt)>160:
                st.error(f"{style}: Текст >160 символов ({len(txt)})")
            if " ты " in (head+txt).lower():
                st.error(f"{style}: Замените «ты» на «вы»")

            final[style] = {"headline": head, "ad_text": txt}

        submitted = st.form_submit_button("Сохранить креативы")
        if submitted:
            st.session_state["final_creatives"] = final
            st.success("Креативы сохранены!")

    # Финальный вывод
    if "final_creatives" in st.session_state:
        st.header("8. Готовые креативы")
        for style, blk in st.session_state["final_creatives"].items():
            st.subheader(style)
            st.markdown(f"**Заголовок:** {blk['headline']}")
            st.markdown(f"**Текст:** {blk['ad_text']}")
            st.divider()
