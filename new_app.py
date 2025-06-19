import streamlit as st
import logging
from urllib.parse import urlparse

from llm_as_judge import LLMAsJudge
from factory import get_parser
from moderation import CreativeGenerator
from mistralai import Mistral

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_creative(headline: str, ad_text: str) -> list[str]:
    errs = []
    if len(headline) > CreativeGenerator.MAX_HEADLINE:
        errs.append(f"Заголовок слишком длинный: {len(headline)}/{CreativeGenerator.MAX_HEADLINE}")
    if len(ad_text) > CreativeGenerator.MAX_AD_TEXT:
        errs.append(f"Текст слишком длинный: {len(ad_text)}/{CreativeGenerator.MAX_AD_TEXT}")
    if " ты " in (headline + " " + ad_text).lower():
        errs.append("Обнаружено обращение «ты», замените на «вы»")
    return errs

st.set_page_config(page_title="Ad Creative Playground", layout="centered")
st.title("Ad Creative Playground")

st.header("1. Как получить API-ключ")
st.markdown("""
1. Зарегистрируйтесь на https://console.mistral.ai/api-keys  
2. Перейдите в раздел **API Keys**.  
3. Скопируйте ключ и сохраните его.
""")

st.header("2. Введите ваш API-ключ")
api_key = st.text_input("API Key", type="password", placeholder="sk-...")

st.header("3. Выберите модель")
model_options = [
    "mistral-large-latest",
    "mistral-small-latest",
    "open-mistral-7b"
]
st.session_state.setdefault("selected_model", model_options[0])
st.session_state["selected_model"] = st.selectbox(
    "Модель",
    model_options,
    index=model_options.index(st.session_state["selected_model"])
)

client = Mistral(api_key=api_key)

for key in ("parsed_data", "judge_output", "user_prompt", "generated_creatives"):  
    if key not in st.session_state:
        st.session_state[key] = None

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
            llm = LLMAsJudge(client=client, model=st.session_state["selected_model"], url=url_input)
            judge_out = llm.extract_key_aspects(parsed)
            st.session_state["judge_output"] = judge_out

if st.session_state.get("judge_output"):
    out = st.session_state["judge_output"]
    st.text_input(
        label="Название",
        value=out.get("brand_name", ""),
        help="При необходимости отредактируйте название",
        key="brand_input"
    )
    themes = out.get("themes", [])
    st.multiselect(
        label="Чем вы занимаетесь",
        options=themes,
        default=themes,
        key="selected_categories",
        help="Отметьте релевантные категории"
    )
    st.header("5. Опишите рекламируемый объект своими словами")
    st.text_area(
        "Ваш промпт",
        placeholder=out.get("prompt", ""),
        height=150,
        key="user_prompt"
    )

if st.session_state.get("user_prompt"):
    if st.button("6. Сгенерировать креативы"):
        with st.spinner("Генерация креативов…"):
            gen = CreativeGenerator(
                client=client,
                model=st.session_state["selected_model"],
                url=url_input
            )
            creatives = gen.generate_creatives(
                st.session_state["user_prompt"],
                st.session_state["judge_output"]
            )
            st.session_state["generated_creatives"] = creatives
            for i in (2, 3):
                st.session_state[f"show_style{i}"] = False

if st.session_state.get("generated_creatives"):
    gen = CreativeGenerator(
        client=client,
        model=st.session_state["selected_model"],
        url=url_input
    )
    creatives = st.session_state["generated_creatives"]
    
    for idx, style in enumerate(["Стиль 1", "Стиль 2", "Стиль 3"], start=1):
        if idx > 1 and not st.session_state.get(f"show_style{idx}", False):
            if st.button(f"Показать {style}", key=f"show_{style}"):
                st.session_state[f"show_style{idx}"] = True
        if idx == 1 or st.session_state.get(f"show_style{idx}", False):
            st.subheader(style)
            head_key, text_key = f"edit_h{idx}", f"edit_t{idx}"
            head = st.text_input(
                f"Заголовок (≤{CreativeGenerator.MAX_HEADLINE})",
                value=creatives[style]["headline"],
                key=head_key
            )
            text = st.text_area(
                f"Текст (≤{CreativeGenerator.MAX_AD_TEXT})",
                value=creatives[style]["ad_text"],
                height=80,
                key=text_key
            )
            errs = validate_creative(head, text)
            for err in errs:
                st.error(f"{style}: {err}")
            st.session_state["generated_creatives"][style] = {"headline": head, "ad_text": text}

            c1, c2 = st.columns(2)
            if c1.button(f"Перегенерировать {style}", key=f"regen_{style}"):
                with st.spinner(f"Перегенерация {style}…"):
                    new_blk = gen.generate_style(
                        st.session_state["user_prompt"],
                        st.session_state["judge_output"],
                        style
                    )
                    st.session_state["generated_creatives"][style] = new_blk
                    errs_new = validate_creative(new_blk["headline"], new_blk["ad_text"])
                    for err in errs_new:
                        st.error(f"{style}: {err}")
            if idx < 3 and c2.button(f"Показать стиль {idx+1}", key=f"show_next_{idx+1}"):
                st.session_state[f"show_style{idx+1}"] = True
