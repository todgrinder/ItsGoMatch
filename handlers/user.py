"""
Обработчики: /delete_me — удаление пользовательских данных.
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import aiosqlite

from keyboards.inline import confirm_kb, main_menu_kb
from database import queries as db_queries

router = Router()


@router.message(Command("delete_me"))
async def cmd_delete_me(message: Message, db: aiosqlite.Connection):
    """Удаление всех данных пользователя."""
    user_id = message.from_user.id
    
    # Проверяем, существует ли пользователь
    user = await db_queries.get_user(db, user_id)
    if not user:
        await message.answer(
            "❌ Вы ещё не зарегистрированы.\n\n"
            "Используйте /start для регистрации."
        )
        return
    
    # Получаем статистику для отображения
    user_groups = await db_queries.get_user_groups(db, user_id)
    user_elements = await db_queries.get_all_user_active_elements(db, user_id)
    pending_requests = await db_queries.get_pending_requests_for_user(db, user_id)
    incoming_requests = await db_queries.get_incoming_requests_for_user(db, user_id)
    
    await message.answer(
        "⚠️ <b>Вы уверены, что хотите удалить аккаунт?</b>\n\n"
        "Будут удалены:\n"
        f"• Ваш профиль ({user.get('username', 'Без имени')})\n"
        f"• Активные элементы: {len(user_elements)}\n"
        f"• Участие в группах: {len(user_groups)}\n"
        f"• Отправленные запросы: {len(pending_requests)}\n"
        f"• Входящие запросы: {len(incoming_requests)}\n\n"
        "Это действие <b>необратимо</b>!",
        reply_markup=confirm_kb("delete_user", user_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("confirm:delete_user:"))
async def cb_confirm_delete(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    """Подтверждение удаления."""
    user_id = int(callback.data.split(":")[2])
    
    # Проверяем, что удаляет сам себя
    if callback.from_user.id != user_id:
        await callback.answer("❌ Вы не можете удалить чужой аккаунт!", show_alert=True)
        return
    
    # Очищаем FSM state
    await state.clear()
    
    # Удаляем пользователя из БД (каскадно удалятся все связанные данные)
    await db_queries.delete_user(db, user_id)
    
    # Логируем действие
    await db_queries.create_log(db, "user_deleted", f"user_id={user_id}")
    
    await callback.message.edit_text(
        "✅ <b>Ваши данные успешно удалены.</b>\n\n"
        "Спасибо, что пользовались ботом!\n"
        "Чтобы начать заново, введите /start",
        parse_mode="HTML"
    )
    await callback.answer("Данные удалены")
