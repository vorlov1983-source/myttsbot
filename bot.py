import os
import tempfile
import telebot
from google import genai
from google.genai import types

# ----- ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (ЗАДАЮТСЯ В ПАНЕЛИ AMVERA) -----
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not TELEGRAM_TOKEN or not GOOGLE_API_KEY:
    raise ValueError("❌ Не заданы переменные TELEGRAM_TOKEN или GOOGLE_API_KEY")

# ----- GEMINI (через Artemox) -----
client = genai.Client(
    api_key=GOOGLE_API_KEY,
    http_options=types.HttpOptions(base_url='https://api.artemox.com')
)

# ----- ТЕЛЕГРАМ БОТ (прямое подключение) -----
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ----- ГОЛОСА -----
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
    bot.send_message(call.message.chat.id, f"✅ Выбран голос: {voice_name}\nТеперь отправьте текст.")

@bot.message_handler(func=lambda message: True)
def text_to_speech(message):
    text = message.text.strip()
    if not text:
        return
    bot.send_chat_action(message.chat.id, 'record_audio')
    voice = user_voice.get(message.from_user.id, "Kore")
    model_name = "gemini-2.5-flash-preview-tts"
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                    )
                ),
            )
        )
        audio_data = response.candidates[0].content.parts[0].inline_data.data
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
        with open(tmp_path, 'rb') as audio:
            bot.send_voice(message.chat.id, audio, reply_to_message_id=message.message_id)
        os.remove(tmp_path)
    except Exception as e:
        print(f"❌ Ошибка TTS: {e}")
        bot.reply_to(message, "Не удалось озвучить текст. Попробуйте другой голос.")

if __name__ == "__main__":
    print("✅ Бот запущен")
    bot.infinity_polling()
