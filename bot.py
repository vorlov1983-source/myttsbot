import os
import tempfile
import telebot
import requests
import base64

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not TELEGRAM_TOKEN or not GOOGLE_API_KEY:
    raise ValueError("❌ Не заданы переменные")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

VOICES = {
    "👩 Kore": "Kore",
    "👩 Aoede": "Aoede",
    "👨 Puck": "Puck",
    "👨 Charon": "Charon",
}
user_voice = {}

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup()
    for name, code in VOICES.items():
        markup.add(telebot.types.InlineKeyboardButton(name, callback_data=code))
    bot.send_message(message.chat.id, "🎤 Выбери голос:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in VOICES.values())
def set_voice(call):
    user_voice[call.from_user.id] = call.data
    bot.answer_callback_query(call.id, "✅ Голос сохранён")
    bot.send_message(call.message.chat.id, "Отправь текст для озвучки.")

@bot.message_handler(func=lambda message: True)
def text_to_speech(message):
    text = message.text.strip()
    if not text:
        return
    bot.send_chat_action(message.chat.id, 'record_audio')
    voice = user_voice.get(message.from_user.id, "Kore")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={GOOGLE_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"]
        },
        "speechConfig": {
            "voiceConfig": {
                "prebuiltVoiceConfig": {"voiceName": voice}
            }
        }
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: {resp.text}")
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
        print("Ошибка:", e)
        bot.reply_to(message, "Не удалось озвучить текст. Попробуй другой голос или позже.")

if __name__ == "__main__":
    print("✅ Бот запущен")
    bot.infinity_polling()
