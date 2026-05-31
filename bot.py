import os
import tempfile
import telebot
import torch

# ----- ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ -----
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("❌ Не задана переменная TELEGRAM_TOKEN в панели Amvera")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ----- ИНИЦИАЛИЗАЦИЯ ЛОКАЛЬНОГО SILERO TTS -----
device = torch.device('cpu')
local_model_path = 'model.pt'

# Если модели еще нет в папке, бот сам скачает её один раз (около 50 МБ)
if not os.path.exists(local_model_path):
    print("⏳ Загрузка качественной модели Silero TTS...")
    torch.hub.download_url_to_file('https://silero.ai', local_model_path)

# Загружаем модель в память
model = torch.package.PackageImporter(local_model_path).load_pickle('tts_models', 'model')
model.to(device)

# Отличные русские голоса, которые встроены в модель
VOICES = {
    "👩 Женский (Ксения)": "kseniya",
    "👩 Женский (Байкал)": "baya",
    "👨 Мужской (Айрат)": "aidar",
}
user_voice = {}
SAMPLE_RATE = 48000  # Студийное качество звука

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup()
    for name, code in VOICES.items():
        markup.add(telebot.types.InlineKeyboardButton(name, callback_data=code))
    bot.send_message(message.chat.id, "🎤 Выберите голос для озвучки русского текста:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in VOICES.values())
def set_voice(call):
    user_voice[call.from_user.id] = call.data
    voice_name = [n for n, c in VOICES.items() if c == call.data][0]
    bot.answer_callback_query(call.id, f"✅ Выбран: {voice_name}")
    bot.send_message(call.message.chat.id, f"✅ Установлен голос: {voice_name}\nТеперь отправьте текст для озвучки.")

@bot.message_handler(func=lambda message: True)
def text_to_speech(message):
    text = message.text.strip()
    if not text:
        return
    
    bot.send_chat_action(message.chat.id, 'record_audio')
    speaker = user_voice.get(message.from_user.id, "kseniya")
    
    try:
        # Генерируем аудио прямо на процессоре Amvera без внешних API
        audio_path = model.save_wav(text=text, speaker=speaker, sample_rate=SAMPLE_RATE)
        
        # Отправляем готовый сгенерированный файл пользователю
        with open(audio_path, 'rb') as audio:
            bot.send_voice(message.chat.id, audio, reply_to_message_id=message.message_id)
            
        # Удаляем временный файл, чтобы не забивать диск хостинга
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
    except Exception as e:
        print(f"❌ Ошибка Silero TTS: {e}")
        bot.reply_to(message, "Не удалось озвучить текст. Попробуйте написать что-то покороче.")

if __name__ == "__main__":
    print("✅ Автономный бот Silero TTS успешно запущен!")
    bot.infinity_polling()
