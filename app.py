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

def validate_creative(headline: str, ad_text: str) -> list[str]:
    """
    Проверяет headline и ad_text на основные правила:
      - длина заголовка ≤40
      - длина текста ≤160
      - нет слова 'ты'
    Возвращает список сообщений об ошибках.
    """
    errs = []
    if len(headline) > 40:
        errs.append(f"Заголовок слишком длинный: {len(headline)}/40")
    if len(ad_text) > 160:
        errs.append(f"Текст слишком длинный: {len(ad_text)}/160")
    if " ты " in (headline + " " + ad_text).lower():
        errs.append("Использовано обращение «ты», замените на «вы»")
    return errs

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
        value=out.get("brand_name", ""),
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
if st.session_state.get("user_prompt"):
    if st.button("6. Сгенерировать креативы"):
        with st.spinner("Генерация…"):
            gen = CreativeGenerator(
                client=client,
                model=st.session_state["selected_model"],
                url=url_input
            )
            st.session_state["generated_creatives"] = gen.generate_creatives(
                st.session_state["user_prompt"],
                st.session_state["judge_output"]
            )
            # сброс прогресса показа следующих стилей
            st.session_state["show_style2"] = False
            st.session_state["show_style3"] = False

# 7) Пошаговый показ, редакция, перегенерация и валидация
creative = st.session_state.get("generated_creatives")
if creative:
    gen = CreativeGenerator(client, st.session_state["selected_model"], url_input)

    # ---- Стиль 1 ----
    st.subheader("Стиль 1 – содержательный")
    head1 = st.text_input(
        "Заголовок (≤40)", 
        value=creative["Стиль 1"]["headline"], 
        key="edit_h1"
    )
    text1 = st.text_area(
        "Текст (≤160)", 
        value=creative["Стиль 1"]["ad_text"], 
        height=80, 
        key="edit_t1"
    )
    errs1 = validate_creative(head1, text1)
    for err in errs1:
        st.error(f"Стиль 1: {err}")
    # Сохраняем правки
    st.session_state["generated_creatives"]["Стиль 1"] = {"headline": head1, "ad_text": text1}

    c1, c2 = st.columns(2)
    if c1.button("Перегенерировать стиль 1"):
        with st.spinner("Перегенерация стиль 1…"):
            new1 = gen.generate_style(
                st.session_state["user_prompt"],
                st.session_state["judge_output"],
                "Стиль 1"
            )
            st.session_state["generated_creatives"]["Стиль 1"] = new1

    if c2.button("Показать стиль 2"):
        st.session_state["show_style2"] = True

    # ---- Стиль 2 ----
    if st.session_state.get("show_style2"):
        st.subheader("Стиль 2 – цепляющий")
        head2 = st.text_input(
            "Заголовок (≤40)", 
            value=creative["Стиль 2"]["headline"], 
            key="edit_h2"
        )
        text2 = st.text_area(
            "Текст (≤160)", 
            value=creative["Стиль 2"]["ad_text"], 
            height=80, 
            key="edit_t2"
        )
        errs2 = validate_creative(head2, text2)
        for err in errs2:
            st.error(f"Стиль 2: {err}")
        st.session_state["generated_creatives"]["Стиль 2"] = {"headline": head2, "ad_text": text2}

        c1, c2 = st.columns(2)
        if c1.button("Перегенерировать стиль 2"):
            with st.spinner("Перегенерация стиль 2…"):
                new2 = gen.generate_style(
                    st.session_state["user_prompt"],
                    st.session_state["judge_output"],
                    "Стиль 2"
                )
                st.session_state["generated_creatives"]["Стиль 2"] = new2

        if c2.button("Показать стиль 3"):
            st.session_state["show_style3"] = True

    # ---- Стиль 3 ----
    if st.session_state.get("show_style3"):
        st.subheader("Стиль 3 – короткий")
        head3 = st.text_input(
            "Заголовок (≤40)", 
            value=creative["Стиль 3"]["headline"], 
            key="edit_h3"
        )
        text3 = st.text_area(
            "Текст (≤160)", 
            value=creative["Стиль 3"]["ad_text"], 
            height=80, 
            key="edit_t3"
        )
        errs3 = validate_creative(head3, text3)
        for err in errs3:
            st.error(f"Стиль 3: {err}")
        st.session_state["generated_creatives"]["Стиль 3"] = {"headline": head3, "ad_text": text3}

        if st.button("Перегенерировать стиль 3"):
            with st.spinner("Перегенерация стиль 3…"):
                new3 = gen.generate_style(
                    st.session_state["user_prompt"],
                    st.session_state["judge_output"],
                    "Стиль 3"
                )
                st.session_state["generated_creatives"]["Стиль 3"] = new3


# # 6) Генерация креативов
# if st.session_state["user_prompt"]:
#     if st.button("6. Сгенерировать рекламные тексты"):
#         with st.spinner("Генерация креативов…"):
#             gen = CreativeGenerator(
#                 client=client,
#                 model=st.session_state["selected_model"],
#                 url=url_input
#             )
#             creat = gen.generate_creatives(st.session_state["user_prompt"])
#             st.session_state["generated_creatives"] = creat

# # 7) Редактирование и финальный вывод
# if st.session_state["generated_creatives"]:
#     st.header("7. Проверьте и отредактируйте креативы")
#     with st.form("edit_creatives_form"):
#         final = {}
#         for style in ["Стиль 1","Стиль 2","Стиль 3"]:
#             block = st.session_state["generated_creatives"].get(style, {})
#             # если телеграм-ресурс — заголовок брендовый
#             default_head = (
#                 st.session_state["parsed_data"].get("title","")
#                 if "t.me" in url_input else
#                 block.get("headline","")
#             )
#             head = st.text_input(f"{style} — Заголовок (≤40):", value=default_head, key=f"{style}_h")
#             txt = st.text_area(f"{style} — Текст (≤160):", value=block.get("ad_text",""), key=f"{style}_t", height=100)

#             # базовая валидация
#             if len(head)>40:
#                 st.error(f"{style}: Заголовок >40 символов ({len(head)})")
#             if len(txt)>160:
#                 st.error(f"{style}: Текст >160 символов ({len(txt)})")
#             if " ты " in (head+txt).lower():
#                 st.error(f"{style}: Замените «ты» на «вы»")

#             final[style] = {"headline": head, "ad_text": txt}

#         submitted = st.form_submit_button("Сохранить креативы")
#         if submitted:
#             st.session_state["final_creatives"] = final
#             st.success("Креативы сохранены!")

#     # Финальный вывод
#     if "final_creatives" in st.session_state:
#         st.header("8. Готовые креативы")
#         for style, blk in st.session_state["final_creatives"].items():
#             st.subheader(style)
#             st.markdown(f"**Заголовок:** {blk['headline']}")
#             st.markdown(f"**Текст:** {blk['ad_text']}")
#             st.divider()
