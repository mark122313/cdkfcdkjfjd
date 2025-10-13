import json
import uuid
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

API_TOKEN = ""

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

LINKS_FILE = "user_links.json"
BLOCKED_FILE = "blocked_users.json"

# Username пользователя flaskiy
FLASKIY_USERNAME = "flaskiy"  # Замените на ваш реальный username

# === Машина состояний ===
class AnonymousState(StatesGroup):
    waiting_message = State()


class ReplyState(StatesGroup):
    waiting_reply = State()


# === Загрузка данных из файлов ===
try:
    with open(LINKS_FILE, "r") as f:
        user_links = json.load(f)
except Exception:
    user_links = {}

try:
    with open(BLOCKED_FILE, "r") as f:
        blocked_users = json.load(f)
except Exception:
    blocked_users = {}

link_to_user = {v: int(k) for k, v in user_links.items()}


def save_links():
    with open(LINKS_FILE, "w") as f:
        json.dump(user_links, f)


def save_blocked():
    with open(BLOCKED_FILE, "w") as f:
        json.dump(blocked_users, f)


# === Проверка блокировки ===
def is_blocked(blocker_id: int, blocked_id: int) -> bool:
    blocker_str = str(blocker_id)
    blocked_str = str(blocked_id)
    return blocker_str in blocked_users and blocked_str in blocked_users[blocker_str]


# === Блокировка пользователя ===
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


# === Кнопки для сообщений ===
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

    # создаём уникальную ссылку при первом запуске
    if user_id not in user_links:
        link_id = str(uuid.uuid4().int)[:10]
        user_links[user_id] = link_id
        link_to_user[link_id] = int(user_id)
        save_links()
    else:
        link_id = user_links[user_id]

    # проверяем, пришёл ли параметр start (т.е. переход по чужой ссылке)
    parts = message.text.split()
    start_param = parts[1] if len(parts) > 1 else None

    if start_param:
        if start_param in link_to_user:
            owner_id = link_to_user[start_param]
            if owner_id == int(user_id):
                await message.answer("⚠️ Это ваша собственная ссылка!")
                return

            # Проверяем блокировку
            if is_blocked(owner_id, int(user_id)):
                await message.answer("❌ Вы заблокированы этим пользователем и не можете отправлять ему сообщения.")
                return

            await state.update_data(owner_id=owner_id)
            await state.set_state(AnonymousState.waiting_message)
            await message.answer(
                "✏️ Теперь вы можете отправлять анонимные сообщения!\n\n"
                "📝 Поддерживаемые типы сообщений:\n"
                "• Текст\n• Фото\n• Видео\n• Голосовые сообщения\n"
                "• Видеосообщения (круглые видео)\n• Стикеры\n\n"
                "Отправьте любое сообщение:"
            )
            return
        else:
            await message.answer("❌ Неверная или устаревшая ссылка.")
            return

    link = f"https://t.me/arzbuybot_bot?start={link_id}"
    await message.answer(
        f"🔗 Ваша личная ссылка для анонимных сообщений:\n{link}\n\n"
        "Поделитесь этой ссылкой с друзьями, чтобы получать анонимные сообщения!"
    )


# === Отправка анонимного сообщения ===
@dp.message(StateFilter(AnonymousState.waiting_message))
async def handle_anonymous(message: types.Message, state: FSMContext):
    data = await state.get_data()
    owner_id = data["owner_id"]
    
    # Проверяем блокировку перед отправкой
    if is_blocked(owner_id, message.from_user.id):
        await message.answer("❌ Вы заблокированы этим пользователем и не можете отправлять ему сообщения.")
        await state.clear()
        return
    
    keyboard = reply_keyboard(message.from_user.id)

    try:
        if message.text:
            await bot.send_message(owner_id, f"💌 Анонимное сообщение:\n{message.text}", reply_markup=keyboard)
        
        elif message.photo:
            caption = message.caption or "💌 Анонимное фото"
            await bot.send_photo(owner_id, message.photo[-1].file_id, caption=caption, reply_markup=keyboard)
        
        elif message.voice:
            await bot.send_voice(owner_id, message.voice.file_id, caption="💌 Анонимное голосовое", reply_markup=keyboard)
        
        elif message.video:
            caption = message.caption or "💌 Анонимное видео"
            await bot.send_video(owner_id, message.video.file_id, caption=caption, reply_markup=keyboard)
        
        elif message.video_note:
            # Отправляем видеосообщение
            await bot.send_video_note(owner_id, message.video_note.file_id)
            # Отправляем отдельное сообщение с информацией
            info_text = "💌 Анонимное видеосообщение"
            if message.caption:
                info_text += f"\n\n📝 Подпись: {message.caption}"
            await bot.send_message(owner_id, info_text, reply_markup=keyboard)
        
        elif message.sticker:
            await bot.send_sticker(owner_id, message.sticker.file_id)
            await bot.send_message(owner_id, "💌 Стикер от анонима", reply_markup=keyboard)
        
        elif message.document:
            caption = message.caption or "💌 Анонимный документ"
            await bot.send_document(owner_id, message.document.file_id, caption=caption, reply_markup=keyboard)
        
        elif message.audio:
            caption = message.caption or "💌 Анонимное аудио"
            await bot.send_audio(owner_id, message.audio.file_id, caption=caption, reply_markup=keyboard)
        
        else:
            await message.answer("⚠️ Этот тип сообщения пока не поддерживается.")
            return

        await message.answer("✅ Сообщение отправлено анонимно!")
    
    except Exception as e:
        await message.answer("❌ Произошла ошибка при отправке сообщения. Попробуйте еще раз.")
        print(f"Error sending message: {e}")
    
    finally:
        await state.clear()


# === Обработка кнопки "Ответить" ===
@dp.callback_query(F.data.startswith("reply:"))
async def handle_reply_button(callback: CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split(":")[1])
    
    # Проверяем блокировку перед ответом
    if is_blocked(target_id, callback.from_user.id):
        await callback.answer("❌ Вы заблокированы этим пользователем.", show_alert=True)
        return
    
    await state.update_data(target_id=target_id)
    await state.set_state(ReplyState.waiting_reply)

    await callback.message.answer(
        "✏️ Теперь вы можете ответить анонимно!\n\n"
        "Отправьте любое сообщение для ответа:"
    )
    await callback.answer()  # убираем "часики" на кнопке


# === Обработка кнопки "Заблокировать" ===
@dp.callback_query(F.data.startswith("block:"))
async def handle_block_button(callback: CallbackQuery):
    blocked_id = int(callback.data.split(":")[1])
    blocker_id = callback.from_user.id
    
    # Блокируем пользователя
    block_user(blocker_id, blocked_id)
    
    await callback.answer("✅ Пользователь заблокирован! Он больше не сможет вам писать.", show_alert=True)
    
    # Убираем кнопки из сообщения
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass  # Если не получилось изменить сообщение - не страшно


# === Обработка секретной кнопки ===
@dp.callback_query(F.data.startswith("secret:"))
async def handle_secret_button(callback: CallbackQuery):
    # Проверяем, что нажал именно flaskiy
    if not is_flaskiy(callback.from_user):
        await callback.answer("❌ У вас нет доступа к этой кнопке!", show_alert=True)
        return
    
    target_id = int(callback.data.split(":")[1])
    
    # Секретное действие для flaskiy
    await callback.answer("🔐 Секретная функция активирована!", show_alert=True)
    
    # Можно добавить любое специальное действие здесь
    # Например, отправить специальное сообщение или выполнить другую функцию
    await callback.message.answer(f"🎯 Секретная функция выполнена для пользователя {target_id}")


# === Обработка анонимного ответа ===
@dp.message(StateFilter(ReplyState.waiting_reply))
async def handle_anonymous_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data["target_id"]
    
    # Проверяем блокировку перед отправкой ответа
    if is_blocked(target_id, message.from_user.id):
        await message.answer("❌ Вы заблокированы этим пользователем и не можете отправлять ему сообщения.")
        await state.clear()
        return
    
    keyboard = reply_keyboard(message.from_user.id)

    try:
        if message.text:
            await bot.send_message(target_id, f"💌 Анонимный ответ:\n{message.text}", reply_markup=keyboard)
        
        elif message.photo:
            caption = message.caption or "💌 Анонимный ответ"
            await bot.send_photo(target_id, message.photo[-1].file_id, caption=caption, reply_markup=keyboard)
        
        elif message.voice:
            await bot.send_voice(target_id, message.voice.file_id, caption="💌 Анонимный ответ", reply_markup=keyboard)
        
        elif message.video:
            caption = message.caption or "💌 Анонимный ответ"
            await bot.send_video(target_id, message.video.file_id, caption=caption, reply_markup=keyboard)
        
        elif message.video_note:
            # Отправляем видеосообщение
            await bot.send_video_note(target_id, message.video_note.file_id)
            # Отправляем отдельное сообщение с информацией
            info_text = "💌 Анонимный ответ (видеосообщение)"
            if message.caption:
                info_text += f"\n\n📝 Подпись: {message.caption}"
            await bot.send_message(target_id, info_text, reply_markup=keyboard)
        
        elif message.sticker:
            await bot.send_sticker(target_id, message.sticker.file_id)
            await bot.send_message(target_id, "💌 Стикер-анонимный ответ", reply_markup=keyboard)
        
        elif message.document:
            caption = message.caption or "💌 Анонимный ответ (документ)"
            await bot.send_document(target_id, message.document.file_id, caption=caption, reply_markup=keyboard)
        
        elif message.audio:
            caption = message.caption or "💌 Анонимный ответ (аудио)"
            await bot.send_audio(target_id, message.audio.file_id, caption=caption, reply_markup=keyboard)
        
        else:
            await message.answer("⚠️ Этот тип сообщения пока не поддерживается.")
            return

        await message.answer("✅ Ваш ответ отправлен анонимно!")
    
    except Exception as e:
        await message.answer("❌ Произошла ошибка при отправке ответа. Попробуйте еще раз.")
        print(f"Error sending reply: {e}")
    
    finally:
        await state.clear()


# === Обработка обычных сообщений (не в состоянии) ===
@dp.message()
async def handle_regular_message(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id in user_links:
        link_id = user_links[user_id]
        link = f"https://t.me/arzbuybot_bot?start={link_id}"
        await message.answer(
            f"🔗 Ваша личная ссылка для анонимных сообщений:\n{link}\n\n"
            "Поделитесь этой ссылкой с друзьями, чтобы получать анонимные сообщения!\n\n"
            "Чтобы отправить анонимное сообщение, перейдите по чужой ссылке."
        )
    else:
        # Если по какой-то причине у пользователя нет ссылки, создаем её
        link_id = str(uuid.uuid4().int)[:10]
        user_links[user_id] = link_id
        link_to_user[link_id] = int(user_id)
        save_links()
        
        link = f"https://t.me/arzbuybot_bot?start={link_id}"
        await message.answer(
            f"🔗 Ваша личная ссылка для анонимных сообщений:\n{link}\n\n"
            "Поделитесь этой ссылкой с друзьями, чтобы получать анонимные сообщения!"
        )


# === Запуск ===
async def main():
    print("🚀 Бот запущен...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
