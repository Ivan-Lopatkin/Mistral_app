import streamlit as st
import requests
import os

st.set_page_config(page_title="Ad Creative Playground", layout="centered")

st.title("Ad Creative Playground")

# 1. Инструкция по получению API ключа
st.header("1. Как получить API-ключ")
st.markdown(
    """
    1. Зарегистрируйтесь на платформе Mistral: https://console.mistral.ai/api-keys
    2. Перейдите в раздел "API Keys" в личном кабинете.
    3. Скопируйте сгенерированный ключ и сохраните его в надёжном месте.
    """
)

# 2. Ввод API ключа
st.header("2. Введите ваш API-ключ")
api_key = st.text_input(
    label="API Key", 
    placeholder="sk-...", 
    type="password"
)

# 3. Выбор модели
st.header("3. Выберите модель")
model = st.selectbox(
    label="Модель",
    options=[
        "mistral-small-latest",
        "mistral-large-latest",
        "open-mistral-7b"
    ],
    index=0
)

# 4. Напишите prompt
st.header("4. Напишите prompt")
prompt = st.text_area(
    label="Prompt",
    height=200,
    placeholder="Например: 'Напиши рекламный текст для лендинга...'")

# 5. Отправка запроса
if st.button("Отправить запрос"):
    if not api_key:
        st.error("Укажите API-ключ перед отправкой запроса.")
    elif not prompt:
        st.error("Заполните поле prompt.")
    else:
        # Формируем тело запроса к Mistral API
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "top_p": 0.9,
            "max_tokens": 256
        }
        with st.spinner("Отправляем запрос..."):
            try:
                response = requests.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                st.subheader("Сгенерированный текст")
                st.write(content)
            except Exception as e:
                st.error(f"Ошибка при запросе: {e}")
