import os
import subprocess
import telebot
import urllib.parse
import requests
from telebot.types import KeyboardButton, ReplyKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

user_modes = {}

@bot.message_handler(commands=["start"])
def start(message):
  markup = ReplyKeyboardMarkup(resize_keyboard=True)
  markup.add(
      KeyboardButton("🔍 Посмотреть EXIF"), KeyboardButton("🧹 Очистить EXIF"), KeyboardButton("🎨 Генерировать изображение")
  )
  bot.reply_to(message, "Выберите режим работы на панели:", reply_markup=markup)


@bot.message_handler(
    func=lambda message: message.text in ["🔍 Посмотреть EXIF", "🧹 Очистить EXIF", "🎨 Генерировать изображение"]
)
def set_mode(message):
  chat_id = message.chat.id
  if message.text == "🔍 Посмотреть EXIF":
    user_modes[chat_id] = "info"
    bot.reply_to(
        message, "Режим просмотра активирован. Отправьте файл документом."
    )

  elif message.text == "🧹 Очистить EXIF":
    user_modes[chat_id] = "clean"
    bot.reply_to(
        message, "Режим очистки активирован. Отправьте файл документом."
    )

  elif message.text == "🎨 Генерировать изображение":
    user_modes[chat_id] = "generate"
    bot.reply_to(
        message, "Режим генерации изображений активирован. Отправьте описание изображения."
    )

@bot.message_handler(content_types=["document"])
def handle_document(message):
  chat_id = message.chat.id
  current_mode = user_modes.get(chat_id, "info")

  if current_mode == "info":
    process_info(message)
  elif current_mode == "clean":
    process_clean(message)
  elif current_mode == "generate":
    process_generate(message)


def process_info(message):
  doc = message.document
  file_name = doc.file_name.lower()

  if not file_name.endswith((".jpg", ".jpeg", ".png", ".mp4", ".mov", ".avi")):
    bot.reply_to(message, "Поддерживаемый формат: jpg, jpeg, png, mp4, mov, avi.")
    return

  sent_msg = bot.reply_to(message, "Загрузка...")
  local_file_path = f"temp/{doc.file_id}_{doc.file_name}"
  txt_file_path = None

  try:
    file_info = bot.get_file(doc.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    os.makedirs("temp", exist_ok=True)

    with open(local_file_path, "wb") as new_file:
      new_file.write(downloaded_file)

    EXIFTOOL_PATH = (
        r"C:\Users\PC\Desktop\exiftool-13.59_64\exiftool-13.59_64\exiftool.exe"
    )

    result = subprocess.run(
        [EXIFTOOL_PATH, local_file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    metadata = result.stdout

    if not metadata:
      bot.edit_message_text(
          "Не удалось извлечь метаданные из файла.",
          chat_id=sent_msg.chat.id,
          message_id=sent_msg.message_id,
      )
      return

    if len(metadata) > 4000:
      txt_file_path = f"temp/metadata_{doc.file_id}.txt"

      with open(txt_file_path, "w", encoding="utf-8") as f:
        f.write(metadata)

      with open(txt_file_path, "rb") as f:
        bot.send_document(
            message.chat.id,
            f,
            caption="📄 Метаданных слишком много, поэтому выгружаю их файлом.",
        )

      bot.delete_message(message.chat.id, sent_msg.message_id)

    else:
      bot.edit_message_text(
          f"```text\n{metadata}\n```",
          chat_id=message.chat.id,
          message_id=sent_msg.message_id,
          parse_mode="Markdown",
      )

  except Exception as e:
    error_text = str(e)
    if "file too big" in error_text or "400" in error_text:
      bot.edit_message_text(
          "Ошибка: Файл слишком большой для обработки. Пожалуйста, попробуйте с"
          " меньшим файлом.",
          chat_id=sent_msg.chat.id,
          message_id=sent_msg.message_id,
      )
    else:
      bot.edit_message_text(
          f"Ошибка {e}", chat_id=sent_msg.chat.id, message_id=sent_msg.message_id
      )

  finally:
    if os.path.exists(local_file_path):
      os.remove(local_file_path)
    if txt_file_path and os.path.exists(txt_file_path):
      os.remove(txt_file_path)


def process_clean(message):
  doc = message.document
  file_name = doc.file_name.lower()

  if not file_name.endswith((".jpg", ".jpeg", ".png", ".mp4", ".mov", ".avi")):
    bot.reply_to(message, "Поддерживаемый формат: jpg, jpeg, png, mp4, mov, avi.")
    return

  sent_msg = bot.reply_to(message, "Очищаю метаданные...")
  local_file_path = f"temp/{doc.file_id}_{doc.file_name}"

  try:
    file_info = bot.get_file(doc.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    os.makedirs("temp", exist_ok=True)

    with open(local_file_path, "wb") as new_file:
      new_file.write(downloaded_file)

    EXIFTOOL_PATH = (
        r"C:\Users\PC\Desktop\exiftool-13.59_64\exiftool-13.59_64\exiftool.exe"
    )

    # Запускаем exiftool для удаления всех метаданных
    subprocess.run(
        [EXIFTOOL_PATH, "-overwrite_original", "-all=", local_file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Отправляем чистый файл пользователю
    with open(local_file_path, "rb") as f:
      bot.send_document(
          message.chat.id, f, caption="✅ Метаданные успешно удалены!"
      )

    # Удаляем служебное сообщение «Очищаю...»
    bot.delete_message(message.chat.id, sent_msg.message_id)

  except Exception as e:
    error_text = str(e)
    if "file too big" in error_text or "400" in error_text:
      bot.edit_message_text(
          "Ошибка: Файл слишком большой для обработки.",
          chat_id=sent_msg.chat.id,
          message_id=sent_msg.message_id,
      )
    else:
      bot.edit_message_text(
          f"Ошибка {e}", chat_id=sent_msg.chat.id, message_id=sent_msg.message_id
      )

  finally:
    # Удаляем файл из папки temp в любом случае
    if os.path.exists(local_file_path):
      os.remove(local_file_path)

@bot.message_handler(content_types=["text"])
def handle_text(message):
  chat_id = message.chat.id
  current_mode = user_modes.get(chat_id, "info")

  # Если пользователь кликнул по кнопкам меню, не считаем это промптом
  if message.text in [
      "🔍 Посмотреть EXIF",
      "🧹 Очистить EXIF",
      "🎨 Генерировать изображение",
  ]:
    return

  if current_mode == "generate":
    process_generate(message)
  else:
    bot.reply_to(
        message,
        "Пожалуйста, выберите режим «🎨 Генерировать изображение» на панели"
        " или отправьте файл.",
    )


def process_generate(message):
  prompt = message.text
  if not prompt:
    bot.reply_to(message, "Пожалуйста, отправьте описание изображения.")
    return

  sent_msg = bot.reply_to(message, "🎨 Отправка запроса к Pollinations.ai...")
  encoded_prompt = urllib.parse.quote(prompt)
  url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"

  try:
    response = requests.get(url, timeout=60)
    if response.status_code == 200:
      os.makedirs("temp", exist_ok=True)
      image_path = f"temp/generated_{message.chat.id}.png"

      with open(image_path, "wb") as f:
        f.write(response.content)

      # Отправляем готовую картинку
      with open(image_path, "rb") as f:
        bot.send_photo(
            message.chat.id, f, caption=f"✅ Запрос: {prompt}"
        )

      # Удаляем служебное сообщение «Отправка запроса...»
      bot.delete_message(message.chat.id, sent_msg.message_id)

      # Удаляем временный файл
      if os.path.exists(image_path):
        os.remove(image_path)
    else:
      if response.status_code == 402:
        bot.edit_message_text(
            "Ошибка: Достигнут лимит запросов к Pollinations.ai. Пожалуйста, попробуйте позже.",
            chat_id=sent_msg.chat.id,
            message_id=sent_msg.message_id,
        )
      else:  
        bot.edit_message_text(
            f"Ошибка сервера: {response.status_code}",
            chat_id=sent_msg.chat.id,
            message_id=sent_msg.message_id,
        )
  except Exception as e:
    bot.edit_message_text(
        f"Ошибка соединения: {e}",
        chat_id=sent_msg.chat.id,
        message_id=sent_msg.message_id,
    )

if __name__ == "__main__":
  print("Бот запущен...")
  bot.infinity_polling()
