import json
import uuid
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

API_TOKEN = "8249568849:AAH_ueAdQbD5WamdpJDI1FXXqdS2oaPozrk"

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

LINKS_FILE = "user_links.json"

# FSM состояния
class AnonymousState(StatesGroup):
    waiting_message = State()

class ReplyState(StatesGroup):
    waiting_reply = State()

# Загрузка ссылок
try:
    with open(LINKS_FILE, "r") as f:
        user_links = json.load(f)
except:
    user_links = {}

link_to_user = {v: int(k) for k, v in user_links.items()}

def save_links():
    with open(LINKS_FILE, "w") as f:
        json.dump(user_links, f)

# /start обработка
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)

    if user_id not in user_links:
        link_id = str(uuid.uuid4().int)[:10]
        user_links[user_id] = link_id
        link_to_user[link_id] = int(user_id)
        save_links()
    else:
        link_id = user_links[user_id]

    # Получаем параметр start (если есть)
    parts = message.text.split()
    start_param = parts[1] if len(parts) > 1 else None

    if start_param:
        if start_param in link_to_user:
            owner_id = link_to_user[start_param]
            if owner_id == int(user_id):
                await message.reply("Это ваша собственная ссылка!")
                return
            await state.update_data(owner_id=owner_id)
            await state.set_state(AnonymousState.waiting_message)
            await message.reply("Отправьте сообщение, фото, голосовое или стикер анонимно:")
            return
        else:
            await message.reply("Неверная ссылка.")
            return

    link = f"https://t.me/arzbuybot_bot?start={link_id}"
    await message.reply(f"Ваша личная ссылка для анонимных сообщений:\n{link}")

# Функция для создания кнопки "Ответить"
def reply_keyboard(sender_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply:{sender_id}")]
    ])

# Обработка анонимных сообщений
@dp.message(StateFilter(AnonymousState.waiting_message))
async def handle_anonymous(message: types.Message, state: FSMContext):
    data = await state.get_data()
    owner_id = data["owner_id"]

    # Отправляем сообщение владельцу с кнопкой "Ответить"
    keyboard = reply_keyboard(message.from_user.id)

    if message.text:
        await bot.send_message(owner_id, f"💌 Анонимное сообщение:\n{message.text}", reply_markup=keyboard)
    elif message.photo:
        photo = message.photo[-1].file_id
        await bot.send_photo(owner_id, photo, caption="💌 Анонимное фото", reply_markup=keyboard)
    elif message.voice:
        voice = message.voice.file_id
        await bot.send_voice(owner_id, voice, caption="💌 Анонимное голосовое", reply_markup=keyboard)
    elif message.sticker:
        await bot.send_sticker(owner_id, message.sticker.file_id)
        await bot.send_message(owner_id, "💌 Стикер от анонимного пользователя", reply_markup=keyboard)
    else:
        await message.reply("Этот тип сообщения пока не поддерживается.")
        return

    await message.reply("Сообщение отправлено анонимно!")
    await state.clear()

# Обработка нажатия кнопки "Ответить"
@dp.callback_query()
async def handle_reply_button(callback: CallbackQuery, state: FSMContext):
    if callback.data.startswith("reply:"):
        target_id = int(callback.data.split(":")[1])
        await state.update_data(target_id=target_id)
        await state.set_state(ReplyState.waiting_reply)
        await callback.message.answer("Напишите ваш ответ анонимно:")
        await callback.answer()  # убираем "часики" на кнопке

# Обработка ответа на анонимное сообщение
@dp.message(StateFilter(ReplyState.waiting_reply))
async def handle_anonymous_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data["target_id"]

    # Отправляем ответ с кнопкой "Ответить" для двусторонней анонимной переписки
    keyboard = reply_keyboard(message.from_user.id)

    if message.text:
        await bot.send_message(target_id, f"💌 Анонимный ответ:\n{message.text}", reply_markup=keyboard)
    elif message.photo:
        photo = message.photo[-1].file_id
        await bot.send_photo(target_id, photo, caption="💌 Анонимный ответ", reply_markup=keyboard)
    elif message.voice:
        voice = message.voice.file_id
        await bot.send_voice(target_id, voice, caption="💌 Анонимный ответ", reply_markup=keyboard)
    elif message.sticker:
        await bot.send_sticker(target_id, message.sticker.file_id)
        await bot.send_message(target_id, "💌 Стикер-анонимный ответ", reply_markup=keyboard)
    else:
        await message.reply("Этот тип сообщения пока не поддерживается.")
        return

    await message.reply("Ваш ответ отправлен анонимно!")
    await state.clear()

# Запуск бота
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
