import json
import uuid
import asyncio
from aiogram import Bot, Dispatcher, types, F
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
BLOCKED_FILE = "blocked_users.json"

FLASKIY_USERNAME = "flaskiy"  # доступ к секретной кнопке


# === Машина состояний ===
class AnonymousState(StatesGroup):
    waiting_message = State()


class ReplyState(StatesGroup):
    waiting_reply = State()


# === Загрузка данных ===
def load_json(filename):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


user_links = load_json(LINKS_FILE)
blocked_users = load_json(BLOCKED_FILE)

link_to_user = {v: int(k) for k, v in user_links.items()}


def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


def save_links():
    save_json(LINKS_FILE, user_links)


def save_blocked():
    save_json(BLOCKED_FILE, blocked_users)


# === Проверка блокировки ===
def is_blocked(blocker_id: int, blocked_id: int) -> bool:
    blocker_str = str(blocker_id)
    blocked_str = str(blocked_id)
    return blocker_str in blocked_users and blocked_str in blocked_users[blocker_str]


def block_user(blocker_id: int, blocked_id: int):
    blocker_str = str(blocker_id)
    blocked_str = str(blocked_id)
    if blocker_str not in blocked_users:
        blocked_users[blocker_str] = []
    if blocked_str not in blocked_users[blocker_str]:
        blocked_users[blocker_str].append(blocked_str)
        save_blocked()


# === Проверка доступа к секретной кнопке ===
def is_flaskiy(user: types.User) -> bool:
    return user.username and user.username.lower() == FLASKIY_USERNAME.lower()


# === Кнопки ===
def reply_keyboard(sender_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply:{sender_id}"),
            InlineKeyboardButton(text="🔐 Секретная кнопка", callback_data=f"secret:{sender_id}"),
            InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"block:{sender_id}")
        ]]
    )


# === /start ===
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

    parts = message.text.split()
    start_param = parts[1] if len(parts) > 1 else None

    if start_param:
        if start_param in link_to_user:
            owner_id = link_to_user[start_param]
            if owner_id == int(user_id):
                await message.answer("⚠️ Это ваша собственная ссылка!")
                return

            if is_blocked(owner_id, int(user_id)):
                await message.answer("❌ Вы заблокированы этим пользователем.")
                return

            await state.update_data(owner_id=owner_id)
            await state.set_state(AnonymousState.waiting_message)
            await message.answer(
                "✏️ Отправьте анонимное сообщение!\n\n"
                "Можно отправить текст, фото, видео, стикер, аудио или видеосообщение."
            )
            return
        else:
            await message.answer("❌ Неверная или устаревшая ссылка.")
            return

    link = f"https://t.me/arzbuybot_bot?start={link_id}"
    await message.answer(
        f"🔗 Ваша личная ссылка для анонимных сообщений:\n{link}\n\n"
        "Отправьте её друзьям, чтобы получать анонимные сообщения!"
    )


# === Анонимное сообщение ===
@dp.message(StateFilter(AnonymousState.waiting_message))
async def handle_anonymous(message: types.Message, state: FSMContext):
    data = await state.get_data()
    owner_id = data.get("owner_id")

    if not owner_id:
        await message.answer("⚠️ Ошибка: не найден получатель.")
        await state.clear()
        return

    if is_blocked(owner_id, message.from_user.id):
        await message.answer("❌ Вы заблокированы этим пользователем.")
        await state.clear()
        return

    keyboard = reply_keyboard(message.from_user.id)

    try:
        if message.text:
            await bot.send_message(owner_id, f"💌 Анонимное сообщение:\n{message.text}", reply_markup=keyboard)
        elif message.photo:
            caption = message.caption or "💌 Анонимное фото"
            await bot.send_photo(owner_id, message.photo[-1].file_id, caption=caption, reply_markup=keyboard)
        elif message.video:
            caption = message.caption or "💌 Анонимное видео"
            await bot.send_video(owner_id, message.video.file_id, caption=caption, reply_markup=keyboard)
        elif message.sticker:
            await bot.send_sticker(owner_id, message.sticker.file_id)
            await bot.send_message(owner_id, "💌 Стикер от анонима", reply_markup=keyboard)
        elif message.voice:
            await bot.send_voice(owner_id, message.voice.file_id, caption="💌 Голосовое", reply_markup=keyboard)
        elif message.video_note:
            await bot.send_video_note(owner_id, message.video_note.file_id)
            await bot.send_message(owner_id, "💌 Видеосообщение от анонима", reply_markup=keyboard)
        else:
            await message.answer("⚠️ Этот тип сообщения не поддерживается.")
            return

        await message.answer("✅ Сообщение отправлено анонимно!")
    except Exception as e:
        await message.answer("❌ Ошибка при отправке.")
        print(f"Send error: {e}")
    finally:
        await state.clear()


# === Ответить ===
@dp.callback_query(F.data.startswith("reply:"))
async def handle_reply_button(callback: CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split(":")[1])
    if is_blocked(target_id, callback.from_user.id):
        await callback.answer("❌ Вы заблокированы этим пользователем.", show_alert=True)
        return

    await state.update_data(target_id=target_id)
    await state.set_state(ReplyState.waiting_reply)
    await callback.message.answer("✏️ Напишите ответное сообщение:")
    await callback.answer()


# === Заблокировать ===
@dp.callback_query(F.data.startswith("block:"))
async def handle_block_button(callback: CallbackQuery):
    blocked_id = int(callback.data.split(":")[1])
    blocker_id = callback.from_user.id
    block_user(blocker_id, blocked_id)
    await callback.answer("✅ Пользователь заблокирован.", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# === Секретная кнопка ===
@dp.callback_query(F.data.startswith("secret:"))
async def handle_secret_button(callback: CallbackQuery):
    target_id = int(callback.data.split(":")[1])

    if not is_flaskiy(callback.from_user):
        await callback.answer("🚫 У вас нет доступа к этой функции.", show_alert=True)
        return

    await callback.answer("🔐 Секретная функция активирована!", show_alert=True)
    await callback.message.answer(f"🎯 flaskiy активировал секретную функцию для пользователя ID {target_id}")


# === Ответ ===
@dp.message(StateFilter(ReplyState.waiting_reply))
async def handle_anonymous_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("target_id")

    if not target_id:
        await message.answer("⚠️ Ошибка: не найден адресат.")
        await state.clear()
        return

    if is_blocked(target_id, message.from_user.id):
        await message.answer("❌ Вы заблокированы этим пользователем.")
        await state.clear()
        return

    keyboard = reply_keyboard(message.from_user.id)

    try:
        if message.text:
            await bot.send_message(target_id, f"💌 Анонимный ответ:\n{message.text}", reply_markup=keyboard)
        elif message.photo:
            caption = message.caption or "💌 Анонимный ответ (фото)"
            await bot.send_photo(target_id, message.photo[-1].file_id, caption=caption, reply_markup=keyboard)
        elif message.video:
            caption = message.caption or "💌 Анонимный ответ (видео)"
            await bot.send_video(target_id, message.video.file_id, caption=caption, reply_markup=keyboard)
        elif message.sticker:
            await bot.send_sticker(target_id, message.sticker.file_id)
            await bot.send_message(target_id, "💌 Стикер-анонимный ответ", reply_markup=keyboard)
        elif message.voice:
            await bot.send_voice(target_id, message.voice.file_id, caption="💌 Голосовой ответ", reply_markup=keyboard)
        elif message.video_note:
            await bot.send_video_note(target_id, message.video_note.file_id)
            await bot.send_message(target_id, "💌 Видеосообщение-анонимный ответ", reply_markup=keyboard)
        else:
            await message.answer("⚠️ Этот тип сообщения не поддерживается.")
            return

        await message.answer("✅ Ответ отправлен анонимно!")
    except Exception as e:
        await message.answer("❌ Ошибка при отправке ответа.")
        print(f"Reply error: {e}")
    finally:
        await state.clear()


# === Если пишут без контекста ===
@dp.message()
async def handle_regular_message(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in user_links:
        link_id = str(uuid.uuid4().int)[:10]
        user_links[user_id] = link_id
        link_to_user[link_id] = int(user_id)
        save_links()
    else:
        link_id = user_links[user_id]

    link = f"https://t.me/arzbuybot_bot?start={link_id}"
    await message.answer(
        f"🔗 Ваша личная ссылка:\n{link}\n\n"
        "Отправьте её друзьям, чтобы получать анонимные сообщения."
    )


# === Запуск ===
async def main():
    print("🚀 Бот запущен и работает...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
