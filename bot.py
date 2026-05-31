import os
import tempfile
import telebot
import requests
import base64

# ----- ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (ЗАДАЮТСЯ В ПАНЕЛИ AMVERA) -----
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not TELEGRAM_TOKEN or not GOOGLE_API_KEY:
    raise ValueError("❌ Не заданы переменные TELEGRAM_TOKEN или GOOGLE_API_KEY")

# ----- СОЗДАНИЕ БОТА -----
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ----- ДОСТУПНЫЕ ГОЛОСА (официальные идентификаторы Gemini TTS) -----
VOICES = {
    "👩 Женский (Kore)": "Kore",
    "👩 Женский (Aoede)": "Aoede",
    "👨 Мужской (Puck)": "Puck",
    "👨 Мужской (Charon)": "Charon",
}
user_voice = {}

# ----- КОМАНДА /start -----
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup()
    for name, code in VOICES.items():
        markup.add(telebot.types.InlineKeyboardButton(name, callback_data=code))
    bot.send_message(message.chat.id, "🎤 Выберите голос для озвучки:", reply_markup=markup)

# ----- ОБРАБОТКА ВЫБОРА ГОЛОСА -----
@bot.callback_query_handler(func=lambda call: call.data in VOICES.values())
def set_voice(call):
    user_voice[call.from_user.id] = call.data
    voice_name = [n for n, c in VOICES.items() if c == call.data][0]
    bot.answer_callback_query(call.id, f"✅ Голос сохранён: {voice_name}")
    bot.send_message(call.message.chat.id, f"✅ Выбран голос: {voice_name}\nТеперь отправьте текст для озвучки.")

# ----- ОСНОВНАЯ ЛОГИКА ОЗВУЧКИ -----
@bot.message_handler(func=lambda message: True)
def text_to_speech(message):
    text = message.text.strip()
    if not text:
        return
    bot.send_chat_action(message.chat.id, 'record_audio')
    voice = user_voice.get(message.from_user.id, "Kore")

    # Формируем запрос к Google Gemini TTS
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={GOOGLE_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {"responseModalities": ["AUDIO"]},
        "speechConfig": {
            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
        }
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        audio_b64 = data['candidates'][0]['content']['parts'][0]['inlineData']['data']
        audio_bytes = base64.b64decode(audio_b64)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, 'rb') as f:
            bot.send_voice(message.chat.id, f, reply_to_message_id=message.message_id)

        os.remove(tmp_path)

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        bot.reply_to(message, "Не удалось озвучить текст. Попробуйте другой голос или отправьте текст покороче.")

# ----- ТЕСТОВАЯ КОМАНДА /test ДЛЯ ПРОВЕРКИ КЛЮЧА -----
@bot.message_handler(commands=['test'])
def test_api_key(message):
    test_text = "Привет, это проверка API ключа."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={GOOGLE_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": test_text}]}],
        "generationConfig": {"responseModalities": ["AUDIO"]},
        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}}
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            bot.reply_to(message, "✅ API ключ работает! Google TTS доступен.")
        else:
            bot.reply_to(message, f"❌ Ошибка ключа: {resp.status_code}\n{resp.text[:300]}")
    except Exception as e:
        bot.reply_to(message, f"❌ Не удалось подключиться: {e}")

# ----- ЗАПУСК БОТА -----
if __name__ == "__main__":
    print("✅ Бот запущен и готов к работе")
    bot.infinity_polling()
