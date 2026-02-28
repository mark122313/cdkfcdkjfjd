import logging
import os
from uuid import uuid4

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import aiohttp

# ===== НАСТРОЙКИ =====
# Используйте переменные окружения для продакшена
BOT_TOKEN = "8433506372:AAEfR3QJip-CGMRDFW7uDqrBqh765mgmMoc"  # замените на свой или используйте os.getenv()
API_BASE_URL = "http://bot_1761135469_5520_crypt1c.bothost.ru"  # замените при необходимости (без / в конце)

# Состояния для ConversationHandler (отправка)
AMOUNT, CONFIRM = range(2)

# Временное хранилище данных пользователя (в продакшене используйте БД)
user_data = {}

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С API =====
async def api_balance(user_id: int) -> float:
    """Запрос баланса через API."""
    async with aiohttp.ClientSession() as session:
        # Пример: GET /balance?user_id=123456
        params = {"user_id": user_id}
        async with session.get(f"{API_BASE_URL}/balance", params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("balance", 0.0)
            else:
                logger.error(f"API balance error: {resp.status}")
                return 0.0


async def api_address(user_id: int) -> str:
    """Получение адреса для пополнения."""
    async with aiohttp.ClientSession() as session:
        params = {"user_id": user_id}
        async with session.get(f"{API_BASE_URL}/address", params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("address", "Адрес не найден")
            else:
                return "Ошибка получения адреса"


async def api_history(user_id: int) -> list:
    """История транзакций."""
    async with aiohttp.ClientSession() as session:
        params = {"user_id": user_id}
        async with session.get(f"{API_BASE_URL}/history", params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("transactions", [])
            else:
                return []


async def api_send(user_id: int, to_address: str, amount: float) -> dict:
    """Отправка средств."""
    async with aiohttp.ClientSession() as session:
        payload = {
            "user_id": user_id,
            "to": to_address,
            "amount": amount,
        }
        async with session.post(f"{API_BASE_URL}/send", json=payload) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return {"error": f"Ошибка API: {resp.status}"}


# ===== ОБРАБОТЧИКИ КОМАНД =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветственное сообщение и главное меню."""
    user_id = update.effective_user.id
    # Приветствуем пользователя
    await update.message.reply_text(
        f"👋 Добро пожаловать в криптокошелёк!\n"
        f"Ваш ID: {user_id}\n"
        f"Выберите действие:"
    )
    await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню с inline-кнопками."""
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("💸 Отправить", callback_data="send")],
        [InlineKeyboardButton("📥 Получить", callback_data="receive")],
        [InlineKeyboardButton("📜 История", callback_data="history")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text("Главное меню:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Главное меню:", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатий на кнопки главного меню."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data

    if data == "balance":
        balance = await api_balance(user_id)
        await query.edit_message_text(
            f"💰 Ваш баланс: **{balance} USDT**\n\n",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
            ])
        )

    elif data == "receive":
        address = await api_address(user_id)
        await query.edit_message_text(
            f"📥 Ваш адрес для пополнения:\n`{address}`\n\n"
            "Переведите средства на этот адрес. Баланс обновится автоматически.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
            ])
        )

    elif data == "history":
        transactions = await api_history(user_id)
        if not transactions:
            text = "📜 История пуста."
        else:
            text = "📜 Последние операции:\n"
            for tx in transactions[-5:]:  # последние 5
                text += f"• {tx['date']}: {tx['amount']} → {tx['to']}\n"
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
            ])
        )

    elif data == "settings":
        await query.edit_message_text(
            "⚙️ Настройки:\nЗдесь можно сменить валюту и т.д. (в разработке).",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
            ])
        )

    elif data == "main_menu":
        await show_main_menu(update, context)

    elif data == "send":
        # Начинаем процесс отправки
        await query.edit_message_text(
            "💸 Введите адрес получателя (или нажмите /cancel для отмены):"
        )
        return "SEND_ADDRESS"  # переходим в состояние ввода адреса


# ===== ОТПРАВКА СРЕДСТВ (ConversationHandler) =====
async def send_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало отправки — запрос адреса."""
    await update.message.reply_text("Введите адрес получателя:")
    return AMOUNT


async def send_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем адрес, запрашиваем сумму."""
    address = update.message.text
    context.user_data["recipient"] = address
    await update.message.reply_text("Введите сумму для отправки:")
    return CONFIRM


async def send_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем сумму, показываем подтверждение."""
    try:
        amount = float(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ Неверная сумма. Введите число:")
        return CONFIRM

    context.user_data["amount"] = amount
    recipient = context.user_data["recipient"]

    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_send")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_send")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"📤 Отправка **{amount} USDT** на адрес `{recipient}`\n\nПодтвердите действие:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )
    return ConversationHandler.END


async def send_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка подтверждения отправки."""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_send":
        user_id = update.effective_user.id
        recipient = context.user_data.get("recipient")
        amount = context.user_data.get("amount")

        result = await api_send(user_id, recipient, amount)
        if "error" in result:
            await query.edit_message_text(f"❌ Ошибка: {result['error']}")
        else:
            await query.edit_message_text(
                f"✅ Отправлено {amount} USDT на адрес {recipient}\n"
                f"TxID: `{result.get('txid', 'неизвестно')}`",
                parse_mode="Markdown",
            )
        # Возвращаемся в главное меню
        await show_main_menu(update, context)
    else:
        await query.edit_message_text("❌ Отправка отменена.")
        await show_main_menu(update, context)


async def send_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена отправки."""
    await update.message.reply_text("❌ Отправка отменена.")
    await show_main_menu(update, context)
    return ConversationHandler.END


# ===== ЗАПУСК =====
def main() -> None:
    """Запуск бота."""
    # Создаём приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Обработчик команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))

    # ConversationHandler для отправки
    send_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^send$")],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_amount)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_confirm)],
        },
        fallbacks=[CommandHandler("cancel", send_cancel)],
    )
    application.add_handler(send_conv)

    # Обработчик inline-кнопок (кроме тех, что уже обработаны в send_conv)
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(balance|receive|history|settings|main_menu)$"))
    # Обработчик подтверждения отправки
    application.add_handler(CallbackQueryHandler(send_confirm_callback, pattern="^(confirm_send|cancel_send)$"))

    # Запускаем бота
    print("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
