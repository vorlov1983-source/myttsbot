import os
import tempfile
import telebot
import requests

# ----- ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (ЗАДАЮТСЯ В ПАНЕЛИ AMVERA) -----
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# ----- ПРОВЕРКА НАЛИЧИЯ КЛЮЧЕЙ -----
if not TELEGRAM_TOKEN or not GOOGLE_API_KEY:
    raise ValueError("❌ Не заданы переменные TELEGRAM_TOKEN или GOOGLE_API_KEY в панели Amvera")

# ----- ИНИЦИАЛИЗАЦИЯ ТЕЛЕГРАМ БОТА -----
# Прямое подключение, так как сервер Amvera находится в Варшаве
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ----- ДОСТУПНЫЕ ГОЛОСА ДЛЯ GEMINI TTS -----
VOICES = {
    "👩 Женский (Kore)": "Kore",
    "👨 Мужской (Puck)": "Puck",
}
user_voice = {}

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup()
    for name, code in VOICES.items():
        markup.add(telebot.types.InlineKeyboardButton(name, callback_data=code))
    bot.send_message(message.chat.id, "🎤 Выберите голос:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in VOICES.values())
def set_voice(call):
    user_voice[call.from_user.id] = call.data
    voice_name = [n for n, c in VOICES.items() if c == call.data][0]
    bot.answer_callback_query(call.id, f"✅ Голос: {voice_name}")
    bot.send_message(call.message.chat.id, f"✅ Выбран голос: {voice_name}\nТеперь отправьте текст для озвучки.")

@bot.message_handler(func=lambda message: True)
def text_to_speech(message):
    text = message.text.strip()
    if not text:
        return
    
    bot.send_chat_action(message.chat.id, 'record_audio')
    voice = user_voice.get(message.from_user.id, "Kore")
    
    # Прямой запрос к вашему шлюзу через проверенный API-интерфейс
    url = "https://artemox.com"
    headers = {
        "Authorization": f"Bearer {GOOGLE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice}
                }
            }
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response_data = response.json()
        
        # Безопасное извлечение бинарных данных аудио из ответа шлюза
        audio_base64 = response_data['candidates'][0]['content']['parts'][0]['inlineData']['data']
        import base64
        audio_data = base64.b64decode(audio_base64)
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
            
        with open(tmp_path, 'rb') as audio:
            bot.send_voice(message.chat.id, audio, reply_to_message_id=message.message_id)
            
        os.remove(tmp_path)
        
    except Exception as e:
        print(f"❌ Ошибка TTS через Artemox: {e}")
        # Если упало, выведем ответ сервера для диагностики
        if 'response' in locals() and response:
            print(f"Ответ сервера: {response.text}")
        bot.reply_to(message, "Не удалось озвучить текст. Попробуйте позже или смените голос.")

if __name__ == "__main__":
    print("✅ Бот успешно запущен и готов к озвучке текста...")
    bot.infinity_polling()
