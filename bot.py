import os
import tempfile
import telebot
import requests

# ----- ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ -----
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") # Сюда передается ваш ключ AQ.Ab8...

if not TELEGRAM_TOKEN or not GOOGLE_API_KEY:
    raise ValueError("❌ Не заданы переменные TELEGRAM_TOKEN или GOOGLE_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Голоса, доступные в OpenAI-совместимом формате TTS
VOICES = {
    "👩 Женский базовый (Alloy)": "alloy",
    "👩 Женский нежный (Nova)": "nova",
    "👩 Женский звонкий (Shimmer)": "shimmer",
    "👨 Мужской базовый (Echo)": "echo",
    "👨 Мужской глубокий (Onyx)": "onyx",
    "👨 Мужской спокойный (Fable)": "fable",
}
user_voice = {}

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup()
    for name, code in VOICES.items():
        markup.add(telebot.types.InlineKeyboardButton(name, callback_data=code))
    bot.send_message(message.chat.id, "🎤 Выберите голос для озвучки текста:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in VOICES.values())
def set_voice(call):
    user_voice[call.from_user.id] = call.data
    voice_name = [n for n, c in VOICES.items() if c == call.data][0]
    bot.answer_callback_query(call.id, f"✅ Выбран: {voice_name}")
    bot.send_message(call.message.chat.id, f"✅ Голос установлен: {voice_name}\nТеперь отправьте текст.")

@bot.message_handler(func=lambda message: True)
def text_to_speech(message):
    text = message.text.strip()
    if not text:
        return
    
    bot.send_chat_action(message.chat.id, 'record_audio')
    voice = user_voice.get(message.from_user.id, "alloy")
    
    # Официальный шлюз Google, работающий по OpenAI стандарту звука
    url = "https://googleapis.com"
    headers = {
        "Authorization": f"Bearer {GOOGLE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "tts-1",
        "input": text,
        "voice": voice
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, stream=True)
        
        if response.status_code != 200:
            raise Exception(f"Код {response.status_code}: {response.text}")
            
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
            
        with open(tmp_path, 'rb') as audio:
            bot.send_voice(message.chat.id, audio, reply_to_message_id=message.message_id)
            
        os.remove(tmp_path)
        
    except Exception as e:
        print(f"❌ Ошибка TTS: {e}")
        bot.reply_to(message, "Не удалось озвучить текст. Попробуйте позже.")

if __name__ == "__main__":
    print("✅ Легковесный бот успешно запущен...")
    bot.infinity_polling()
