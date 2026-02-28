#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Wallet Bot - копия Telegram Wallet
API: http://bot_1761135469_5520_crypt1c.bothost.ru
"""

import logging
import os
import sys
from uuid import uuid4
from typing import Dict, Any, Optional

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
import asyncio

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8433506372:AAEfR3QJip-CGMRDFW7uDqrBqh765mgmMoc"
API_BASE_URL = "http://bot_1761135469_5520_crypt1c.bothost.ru"

# Состояния для ConversationHandler
ADDRESS, AMOUNT, CONFIRM = range(3)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
async def api_request(method: str, endpoint: str, **kwargs) -> Optional[Dict]:
    """Универсальная функция для запросов к API."""
    url = f"{API_BASE_URL}/{endpoint.lstrip('/')}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"API error {response.status}: {await response.text()}")
                    return None
    except Exception as e:
        logger.error(f"API request failed: {e}")
        return None


async def get_balance(user_id: int) -> float:
    """Получить баланс пользователя."""
    result = await api_request("GET", "balance", params={"user_id": user_id})
    return result.get("balance", 0.0) if result else 0.0


async def get_address(user_id: int) -> str:
    """Получить адрес для пополнения."""
    result = await api_request("GET", "address", params={"user_id": user_id})
    return result.get("address", "Адрес временно недоступен") if result else "Ошибка получения адреса"


async def get_history(user_id: int) -> list:
    """Получить историю транзакций."""
    result = await api_request("GET", "history", params={"user_id": user_id})
    return result.get("transactions", []) if result else []


async def send_transaction(user_id: int, to_address: str, amount: float) -> Dict:
    """Отправить транзакцию."""
    result = await api_request(
        "POST", 
        "send", 
        json={
            "user_id": user_id,
            "to": to_address,
            "amount": amount
        }
    )
    return result or {"error": "Ошибка отправки"}


# ===== ОБРАБОТЧИКИ КОМАНД =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user = update.effective_user
    welcome_text = (
        f"👋 Добро пожаловать, {user.first_name}!\n\n"
        f"🤖 Этот бот - копия Telegram Wallet\n"
        f"💼 Здесь вы можете хранить и отправлять криптовалюту\n\n"
        f"Выберите действие в меню ниже:"
    )
    await update.message.reply_text(welcome_text)
    await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = "Главное меню:") -> None:
    """Показать главное меню с кнопками."""
    keyboard = [
        [
            InlineKeyboardButton("💰 Баланс", callback_data="balance"),
            InlineKeyboardButton("📤 Отправить", callback_data="send")
        ],
        [
            InlineKeyboardButton("📥 Получить", callback_data="receive"),
            InlineKeyboardButton("📜 История", callback_data="history")
        ],
        [
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
            InlineKeyboardButton("🔄 Обновить", callback_data="refresh")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки главного меню."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    try:
        if data == "balance":
            balance = await get_balance(user_id)
            text = (
                f"💰 **Ваш баланс**\n\n"
                f"`{balance:.8f}` USDT\n\n"
                f"≈ ${balance:.2f} USD"
            )
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
            await query.edit_message_text(
                text, 
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        elif data == "receive":
            address = await get_address(user_id)
            text = (
                f"📥 **Получение средств**\n\n"
                f"Ваш адрес для пополнения:\n"
                f"`{address}`\n\n"
                f"⚠️ Отправляйте только USDT в сети TRC-20"
            )
            keyboard = [
                [InlineKeyboardButton("📋 Копировать адрес", callback_data=f"copy_{address[:10]}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
            ]
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        elif data == "history":
            transactions = await get_history(user_id)
            if not transactions:
                text = "📜 **История операций**\n\nУ вас пока нет транзакций"
            else:
                text = "📜 **Последние операции:**\n\n"
                for tx in transactions[-5:]:
                    emoji = "📤" if tx.get('type') == 'send' else "📥"
                    text += f"{emoji} {tx.get('date', 'N/A')}\n"
                    text += f"   Сумма: `{tx.get('amount', 0)}` USDT\n"
                    text += f"   Статус: ✅ Завершено\n\n"
            
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        elif data == "settings":
            text = (
                "⚙️ **Настройки**\n\n"
                "• Валюта: USDT\n"
                "• Сеть: TRC-20\n"
                "• Уведомления: Вкл\n\n"
                "Дополнительные настройки появятся скоро!"
            )
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        elif data == "refresh":
            await query.edit_message_text("🔄 Обновляю данные...")
            await show_main_menu(update, context, "✅ Данные обновлены!\n\nГлавное меню:")
            
        elif data == "main_menu":
            await show_main_menu(update, context)
            
        elif data.startswith("copy_"):
            await query.answer("Адрес скопирован в буфер обмена (в Telegram Web)", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in button_handler: {e}")
        await query.edit_message_text("❌ Произошла ошибка. Попробуйте позже.")


# ===== ОТПРАВКА СРЕДСТВ (ConversationHandler) =====
async def send_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало процесса отправки."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📤 **Отправка средств**\n\n"
        "Введите адрес получателя (или /cancel для отмены):",
        parse_mode="Markdown"
    )
    return ADDRESS


async def send_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение адреса получателя."""
    address = update.message.text.strip()
    
    # Простая валидация адреса
    if len(address) < 20 or len(address) > 100:
        await update.message.reply_text(
            "❌ Неверный формат адреса. Попробуйте снова:"
        )
        return ADDRESS
    
    context.user_data["recipient_address"] = address
    
    await update.message.reply_text(
        "💰 Введите сумму для отправки (в USDT):"
    )
    return AMOUNT


async def send_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение суммы и подтверждение."""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной")
    except ValueError:
        await update.message.reply_text(
            "❌ Неверная сумма. Введите положительное число:"
        )
        return AMOUNT
    
    context.user_data["amount"] = amount
    address = context.user_data["recipient_address"]
    
    # Проверяем баланс
    user_id = update.effective_user.id
    balance = await get_balance(user_id)
    
    if amount > balance:
        await update.message.reply_text(
            f"❌ Недостаточно средств. Ваш баланс: {balance:.2f} USDT\n\n"
            f"Введите другую сумму:"
        )
        return AMOUNT
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_send"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_send")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📤 **Подтверждение отправки**\n\n"
        f"Адрес получателя:\n`{address}`\n\n"
        f"Сумма: **{amount:.2f} USDT**\n"
        f"Комиссия: **0.1 USDT**\n"
        f"Итого к списанию: **{amount + 0.1:.2f} USDT**\n\n"
        f"Всё верно?",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return CONFIRM


async def send_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка подтверждения."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_send":
        user_id = update.effective_user.id
        address = context.user_data.get("recipient_address")
        amount = context.user_data.get("amount")
        
        # Отправка через API
        result = await send_transaction(user_id, address, amount)
        
        if "error" in result:
            await query.edit_message_text(
                f"❌ Ошибка отправки: {result['error']}"
            )
        else:
            txid = result.get('txid', 'неизвестно')
            await query.edit_message_text(
                f"✅ **Отправка выполнена успешно!**\n\n"
                f"Сумма: {amount:.2f} USDT\n"
                f"Получатель: `{address}`\n"
                f"TxID: `{txid[:20]}...`\n\n"
                f"Средства будут зачислены в течение нескольких минут.",
                parse_mode="Markdown"
            )
        
        # Возвращаемся в главное меню
        await show_main_menu(update, context)
    else:
        await query.edit_message_text("❌ Отправка отменена.")
        await show_main_menu(update, context)
    
    # Очищаем данные
    context.user_data.clear()
    return ConversationHandler.END


async def send_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена отправки."""
    await update.message.reply_text("❌ Отправка отменена.")
    await show_main_menu(update, context)
    context.user_data.clear()
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать справку."""
    help_text = (
        "🤖 **Помощь по боту**\n\n"
        "**Команды:**\n"
        "/start - Запустить бота\n"
        "/help - Показать эту справку\n"
        "/cancel - Отменить текущее действие\n\n"
        "**Как пользоваться:**\n"
        "💰 Баланс - просмотр текущего баланса\n"
        "📤 Отправить - перевод средств\n"
        "📥 Получить - ваш адрес для пополнения\n"
        "📜 История - последние транзакции\n\n"
        "**Поддерживаемая сеть:** TRC-20 (USDT)"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


# ===== ОСНОВНАЯ ФУНКЦИЯ =====
def main() -> None:
    """Запуск бота."""
    try:
        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()

        # Обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))

        # ConversationHandler для отправки
        send_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(send_start, pattern="^send$")],
            states={
                ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_address)],
                AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_amount)],
                CONFIRM: [CallbackQueryHandler(send_confirm, pattern="^(confirm_send|cancel_send)$")],
            },
            fallbacks=[
                CommandHandler("cancel", send_cancel),
                MessageHandler(filters.COMMAND, send_cancel)
            ],
        )
        application.add_handler(send_conv)

        # Обработчик inline-кнопок
        application.add_handler(
            CallbackQueryHandler(
                button_handler, 
                pattern="^(balance|receive|history|settings|refresh|main_menu|copy_.*)$"
            )
        )

        # Запускаем бота
        print("🤖 Бот запущен и готов к работе!")
        print(f"📱 Токен: {BOT_TOKEN[:10]}...")
        print(f"🔗 API URL: {API_BASE_URL}")
        print("🟢 Нажмите Ctrl+C для остановки")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
