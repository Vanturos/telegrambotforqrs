import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from pyzbar.pyzbar import decode
from PIL import Image
import io
import cv2
import numpy as np

# Включение логирования
logging.basicConfig(level=logging.INFO)

Bot_TOKEN = os.environ.get('BOT_TOKEN')  # Убедитесь, что ваш токен хранится в переменной окружения
ADMIN_ID = int(os.environ.get('ADMIN_ID'))  # Убедитесь, что ваш numeric user ID хранится в переменной окружения

bot = Bot(token=Bot_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Создание клавиатуры с кнопками
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Привет"), KeyboardButton(text="Сканировать")],
        [KeyboardButton(text="Связь с разработчиком"), KeyboardButton(text="Помощь")]
    ],
    resize_keyboard=True
)

class BugReport(StatesGroup):
    waiting_for_report = State()

@dp.message(Command(commands=['start']))
async def start_command(message: types.Message):
    await message.answer(
        "Привет! Я простенький бот, который может сканировать QR коды. Вот список моих команд:\n"
        "Привет - просто поздороваться\n"
        "Сканировать - начать сканирование QR-кода\n"
        "Помощь - получить справку о возможностях бота\n"
        "Связь с разработчиком - отправить отчет о ошибке или баге",
        reply_markup=keyboard
    )

@dp.message(lambda message: message.text == "Привет")
async def privet_command(message: types.Message):
    await message.answer('Привет, как делишки?', reply_markup=keyboard)

@dp.message(lambda message: message.text == "Сканировать")
async def check_qr(message: types.Message):
    await message.answer('Я готов сканировать твой QR код. Присылай его!', reply_markup=keyboard)

@dp.message(lambda message: message.text == "Помощь")
async def responsibilities(message: types.Message):
    await message.answer(
        "Вот список моих команд:\n"
        "Привет - просто поздороваться\n"
        "Сканировать - начать сканирование QR-кода\n"
        "Помощь - получить справку о возможностях бота\n"
        "Связь с разработчиком - отправить отчет о ошибке или баге",
        reply_markup=keyboard
    )

@dp.message(lambda message: message.text == "Связь с разработчиком")
async def bug_report(message: types.Message, state: FSMContext):
    await message.answer('Опишите ошибку или баг, который вы обнаружили.', reply_markup=keyboard)
    await state.set_state(BugReport.waiting_for_report)

@dp.message(BugReport.waiting_for_report)
async def process_bug_report(message: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"Багрепорт от {message.from_user.username or message.from_user.full_name}:\n{message.text}")
    await message.answer('Спасибо за ваш отчет! Он был отправлен администратору.', reply_markup=keyboard)
    await state.clear()

async def process_qr(image_bytes):
    # Преобразование байтов в изображение OpenCV
    np_arr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    # Предварительная обработка изображения
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Попытка распознавания QR-кода
    decoded_objects = decode(thresh)
    if not decoded_objects:
        decoded_objects = decode(image)  # Попробуем без обработки, если не найдено
    if decoded_objects:
        return decoded_objects[0].data.decode("utf-8")
    else:
        return None

@dp.message(lambda message: message.content_type == ContentType.PHOTO)
async def handle_photo(message: types.Message):
    file_info = await bot.get_file(message.photo[-1].file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    downloaded_file_bytes = downloaded_file.read()
    qr_data = await process_qr(downloaded_file_bytes)
    if qr_data:
        await message.answer(f'QR код распознан: {qr_data}')
    else:
        await message.answer('QR код не найден на изображении.')

@dp.message(lambda message: message.content_type == ContentType.DOCUMENT)
async def handle_document(message: types.Message):
    file_info = await bot.get_file(message.document.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    downloaded_file_bytes = downloaded_file.read()
    qr_data = await process_qr(downloaded_file_bytes)
    if qr_data:
        await message.answer(f'QR код распознан: {qr_data}')
    else:
        await message.answer('QR код не найден на изображении.')

@dp.message()
async def forward_bug_report(message: types.Message):
    if message.reply_to_message and 'Опишите ошибку или баг' in message.reply_to_message.text:
        await bot.send_message(ADMIN_ID, f"Багрепорт от {message.from_user.username or message.from_user.full_name}:\n{message.text}")
        await message.answer('Спасибо за ваш отчет! Он был отправлен администратору.', reply_markup=keyboard)
    else:
        await message.answer('Для справки по возможностям бота напишите команду /help', reply_markup=keyboard)

async def main():
    dp.message.register(start_command, Command(commands=['start']))
    dp.message.register(privet_command, lambda message: message.text == "Привет")
    dp.message.register(check_qr, lambda message: message.text == "Сканировать")
    dp.message.register(responsibilities, lambda message: message.text == "Помощь")
    dp.message.register(bug_report, lambda message: message.text == "Связь с разработчиком")
    dp.message.register(process_bug_report, BugReport.waiting_for_report)
    dp.message.register(handle_photo, lambda message: message.content_type == ContentType.PHOTO)
    dp.message.register(handle_document, lambda message: message.content_type == ContentType.DOCUMENT)
    dp.message.register(forward_bug_report)
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
