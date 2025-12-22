"""
Обработчики: /accept, /reject запросов на присоединение.
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
import aiosqlite

from config import GENDER_LABELS
from keyboards.inline import (
    requests_list_kb,
    request_detail_kb,
    join_request_kb,
    main_menu_kb,
    manage_element_kb
)
from database import queries as db_queries

router = Router()


# ==================== HELPERS ====================

def format_member_info(member: dict) -> str:
    """Форматировать информацию об участнике."""
    gender_icon = "👨" if member.get("gender") == "male" else "👩" if member.get("gender") == "female" else "👤"
    username = member.get("username", "Без имени")
    rating = member.get("rating", "?")
    return f"{gender_icon} {username} — рейтинг: {rating}"


def format_member_with_contact(member: dict) -> str:
    """Форматировать информацию об участнике с контактом."""
    gender_icon = "👨" if member.get("gender") == "male" else "👩" if member.get("gender") == "female" else "👤"
    username = member.get("username", "Без имени")
    rating = int(member.get("rating", 0))
    telegram_username = member.get("telegram_username")
    
    # Формируем контакт
    if telegram_username:
        contact = f"@{telegram_username}"
    else:
        contact = f"<a href='tg://user?id={member['user_id']}'>написать</a>"
    
    return f"{gender_icon} <b>{username}</b> — рейтинг: {rating}\n   📱 Контакт: {contact}"


async def notify_group_formed(bot: Bot, db: aiosqlite.Connection, group_id: int, event_title: str):
    """Уведомить всех участников о сформированной группе с контактами."""
    # Получаем участников с контактной информацией
    members = await db_queries.get_group_members_with_contacts(db, group_id)
    group = await db_queries.get_group(db, group_id)
    
    if not members:
        return
    
    avg_rating = int(group.get("rating_avg", 0))
    
    # Формируем список участников для каждого получателя
    for recipient in members:
        recipient_id = recipient["user_id"]
        
        # Формируем список других участников (для текущего получателя)
        other_members_text = ""
        for m in members:
            if m["user_id"] != recipient_id:
                other_members_text += f"\n• {format_member_with_contact(m)}"
        
        try:
            if len(members) == 2:
                # Для пары — особое сообщение
                partner = [m for m in members if m["user_id"] != recipient_id][0]
                partner_contact = f"@{partner['telegram_username']}" if partner.get('telegram_username') else f"<a href='tg://user?id={partner['user_id']}'>написать</a>"
                partner_gender = GENDER_LABELS.get(partner.get("gender"), "Не указан")
                partner_rating = int(partner.get("rating", 0))
                
                await bot.send_message(
                    recipient_id,
                    f"🎉 <b>Пара сформирована!</b>\n\n"
                    f"📌 Турнир: <b>{event_title}</b>\n"
                    f"⭐ Средний рейтинг: {avg_rating}\n\n"
                    f"👤 <b>Ваш партнёр:</b>\n"
                    f"• 📛 Имя: {partner.get('username', 'Без имени')}\n"
                    f"• 🚻 Пол: {partner_gender}\n"
                    f"• 📊 Рейтинг: {partner_rating}\n"
                    f"• 📱 Контакт: {partner_contact}\n\n"
                    f"💬 Свяжитесь с партнёром для координации!\n\n"
                    f"Удачи на турнире! 🏆",
                    parse_mode="HTML"
                )
            else:
                # Для команды
                await bot.send_message(
                    recipient_id,
                    f"🎉 <b>Команда сформирована!</b>\n\n"
                    f"📌 Турнир: <b>{event_title}</b>\n"
                    f"⭐ Средний рейтинг команды: {avg_rating}\n"
                    f"👥 Участников: {len(members)}\n\n"
                    f"<b>Ваши тиммейты:</b>"
                    f"{other_members_text}\n\n"
                    f"💬 Свяжитесь с командой для координации!\n\n"
                    f"Удачи на турнире! 🏆",
                    parse_mode="HTML"
                )
        except Exception as e:
            # Логируем ошибку, но продолжаем отправку остальным
            pass


# ==================== КОМАНДЫ ====================

@router.message(Command("accept"))
async def cmd_accept(message: Message, db: aiosqlite.Connection, bot: Bot):
    """Принять запрос: /accept 456."""
    user_id = message.from_user.id
    
    # Обновляем telegram_username
    await db_queries.update_telegram_username(db, user_id, message.from_user.username)
    
    # Проверяем регистрацию
    if not await db_queries.is_profile_complete(db, user_id):
        await message.answer(
            "❌ Сначала завершите регистрацию.\n"
            "Используйте /start"
        )
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "✅ <b>Принять запрос</b>\n\n"
            "Формат: /accept &lt;join_id&gt;\n"
            "Пример: <code>/accept 456</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        join_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ ID запроса должен быть числом.")
        return
    
    # Получаем запрос
    request = await db_queries.get_join_request(db, join_id)
    if not request:
        await message.answer("❌ Запрос не найден.")
        return
    
    if request["status"] != "pending":
        status_text = {
            "accepted": "уже принят",
            "rejected": "уже отклонён",
            "expired": "истёк"
        }.get(request["status"], "недействителен")
        await message.answer(f"❌ Этот запрос {status_text}.")
        return
    
    # Проверяем, что текущий пользователь — владелец элемента
    if request["element_creator_id"] != user_id:
        await message.answer("❌ Вы не являетесь владельцем этой заявки.")
        return
    
    # Принимаем запрос
    result = await db_queries.accept_join_request(db, join_id)
    
    if not result["success"]:
        await message.answer("❌ Не удалось принять запрос. Возможно, заявка уже заполнена.")
        return
    
    # Получаем данные для уведомлений
    requester = await db_queries.get_user(db, request["requester_id"])
    event = await db_queries.get_event(db, request["event_id"])
    
    # Логируем
    await db_queries.create_log(
        db,
        "join_request_accepted",
        f"join_id={join_id}, element_id={request['element_id']}, requester_id={request['requester_id']}"
    )
    
    # Уведомляем отправителя запроса
    try:
        await bot.send_message(
            request["requester_id"],
            f"✅ <b>Ваш запрос принят!</b>\n\n"
            f"📌 Турнир: {event['title']}\n\n"
            f"Вы добавлены в заявку #{request['element_id']}.",
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    # Если группа сформирована, уведомляем всех с контактами
    if result["group_created"]:
        await notify_group_formed(bot, db, result["group_id"], event["title"])
        
        await message.answer(
            f"✅ <b>Запрос #{join_id} принят!</b>\n\n"
            f"🎉 Группа полностью сформирована!\n"
            f"Все участники получили уведомление с контактами друг друга.",
            parse_mode="HTML"
        )
    else:
        members = await db_queries.get_element_members(db, request["element_id"])
        element = await db_queries.get_element(db, request["element_id"])
        spots_left = element["target_size"] - len(members)
        
        await message.answer(
            f"✅ <b>Запрос #{join_id} принят!</b>\n\n"
            f"👤 {requester.get('username', 'Пользователь')} добавлен в заявку.\n"
            f"🪑 Осталось мест: {spots_left}",
            parse_mode="HTML"
        )


@router.message(Command("reject"))
async def cmd_reject(message: Message, db: aiosqlite.Connection, bot: Bot):
    """Отклонить запрос: /reject 456."""
    user_id = message.from_user.id
    
    # Проверяем регистрацию
    if not await db_queries.is_profile_complete(db, user_id):
        await message.answer(
            "❌ Сначала завершите регистрацию.\n"
            "Используйте /start"
        )
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "❌ <b>Отклонить запрос</b>\n\n"
            "Формат: /reject &lt;join_id&gt;\n"
            "Пример: <code>/reject 456</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        join_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ ID запроса должен быть числом.")
        return
    
    # Получаем запрос
    request = await db_queries.get_join_request(db, join_id)
    if not request:
        await message.answer("❌ Запрос не найден.")
        return
    
    if request["status"] != "pending":
        await message.answer("❌ Этот запрос уже обработан.")
        return
    
    # Проверяем, что текущий пользователь — владелец элемента
    if request["element_creator_id"] != user_id:
        await message.answer("❌ Вы не являетесь владельцем этой заявки.")
        return
    
    # Отклоняем запрос
    await db_queries.update_join_request_status(db, join_id, "rejected")
    
    # Получаем данные для уведомления
    event = await db_queries.get_event(db, request["event_id"])
    
    # Логируем
    await db_queries.create_log(
        db,
        "join_request_rejected",
        f"join_id={join_id}, element_id={request['element_id']}, requester_id={request['requester_id']}"
    )
    
    # Уведомляем отправителя запроса
    try:
        await bot.send_message(
            request["requester_id"],
            f"❌ <b>Ваш запрос отклонён</b>\n\n"
            f"📌 Турнир: {event['title']}\n"
            f"Заявка: #{request['element_id']}\n\n"
            f"Вы можете найти другие заявки для присоединения.",
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    await message.answer(f"❌ Запрос #{join_id} отклонён.")


@router.message(Command("my_requests"))
async def cmd_my_requests(message: Message, db: aiosqlite.Connection):
    """Показать входящие запросы."""
    user_id = message.from_user.id
    
    # Проверяем регистрацию
    if not await db_queries.is_profile_complete(db, user_id):
        await message.answer(
            "❌ Сначала завершите регистрацию.\n"
            "Используйте /start"
        )
        return
    
    # Получаем входящие запросы
    incoming = await db_queries.get_incoming_requests_for_user(db, user_id)
    
    if not incoming:
        await message.answer(
            "📥 <b>Входящие запросы</b>\n\n"
            "У вас нет входящих запросов.",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
        return
    
    requests_text = ""
    for req in incoming[:10]:  # Показываем максимум 10
        gender_icon = "👨" if req.get("gender") == "male" else "👩" if req.get("gender") == "female" else "👤"
        requests_text += (
            f"\n• {gender_icon} <b>{req.get('username', 'Без имени')}</b> "
            f"(рейтинг: {req.get('rating', '?')})\n"
            f"  Турнир: {req.get('event_title', '?')}\n"
            f"  /accept {req['join_id']} | /reject {req['join_id']}\n"
        )
    
    await message.answer(
        f"📥 <b>Входящие запросы ({len(incoming)})</b>\n"
        f"{requests_text}",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


# ==================== CALLBACKS ====================

@router.callback_query(F.data.startswith("view_requests:"))
async def cb_view_requests(callback: CallbackQuery, db: aiosqlite.Connection):
    """Просмотр входящих запросов к заявке."""
    element_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Получаем элемент
    element = await db_queries.get_element(db, element_id)
    if not element:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    # Проверяем, что пользователь — создатель
    if element["creator_id"] != user_id:
        await callback.answer("❌ Вы не владелец этой заявки", show_alert=True)
        return
    
    event_id = element["event_id"]
    
    # Получаем запросы
    requests = await db_queries.get_pending_requests_for_element(db, element_id)
    
    await callback.message.edit_text(
        f"📥 <b>Входящие запросы</b>\n\n"
        f"Заявка: #{element_id}\n"
        f"Ожидающих: {len(requests)}",
        reply_markup=requests_list_kb(requests, element_id, event_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_request:"))
async def cb_view_request(callback: CallbackQuery, db: aiosqlite.Connection):
    """Просмотр деталей запроса."""
    join_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Получаем запрос
    request = await db_queries.get_join_request(db, join_id)
    if not request:
        await callback.answer("❌ Запрос не найден", show_alert=True)
        return
    
    # Проверяем, что пользователь — владелец элемента
    if request["element_creator_id"] != user_id:
        await callback.answer("❌ Вы не владелец этой заявки", show_alert=True)
        return
    
    if request["status"] != "pending":
        await callback.answer("❌ Этот запрос уже обработан", show_alert=True)
        return
    
    element_id = request["element_id"]
    gender_label = GENDER_LABELS.get(request.get("gender"), "👤 Не указан")
    
    await callback.message.edit_text(
        f"📨 <b>Запрос #{join_id}</b>\n\n"
        f"👤 От: <b>{request.get('username', 'Без имени')}</b>\n"
        f"🚻 Пол: {gender_label}\n"
        f"📊 Рейтинг: {request.get('rating', '?')}\n\n"
        "Принять этого участника?",
        reply_markup=request_detail_kb(join_id, element_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("accept_request:"))
async def cb_accept_request(callback: CallbackQuery, db: aiosqlite.Connection, bot: Bot):
    """Кнопка «Принять» запрос."""
    join_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Обновляем telegram_username
    await db_queries.update_telegram_username(db, user_id, callback.from_user.username)
    
    # Получаем запрос
    request = await db_queries.get_join_request(db, join_id)
    if not request:
        await callback.answer("❌ Запрос не найден", show_alert=True)
        return
    
    # Проверяем, что пользователь — владелец элемента
    if request["element_creator_id"] != user_id:
        await callback.answer("❌ Вы не владелец этой заявки", show_alert=True)
        return
    
    if request["status"] != "pending":
        await callback.answer("❌ Этот запрос уже обработан", show_alert=True)
        return
    
    # Принимаем запрос
    result = await db_queries.accept_join_request(db, join_id)
    
    if not result["success"]:
        await callback.answer("❌ Не удалось принять запрос", show_alert=True)
        return
    
    # Получаем данные для уведомлений
    requester = await db_queries.get_user(db, request["requester_id"])
    event = await db_queries.get_event(db, request["event_id"])
    
    # Логируем
    await db_queries.create_log(
        db,
        "join_request_accepted",
        f"join_id={join_id}, element_id={request['element_id']}, requester_id={request['requester_id']}"
    )
    
    # Уведомляем отправителя запроса
    try:
        await bot.send_message(
            request["requester_id"],
            f"✅ <b>Ваш запрос принят!</b>\n\n"
            f"📌 Турнир: {event['title']}\n\n"
            f"Вы добавлены в заявку #{request['element_id']}.",
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    await callback.answer("✅ Запрос принят!", show_alert=True)
    
    # Если группа сформирована, уведомляем всех с контактами
    if result["group_created"]:
        await notify_group_formed(bot, db, result["group_id"], event["title"])
        
        await callback.message.edit_text(
            f"✅ <b>Запрос #{join_id} принят!</b>\n\n"
            f"🎉 Группа полностью сформирована!\n"
            f"Все участники получили уведомление с контактами друг друга.\n\n"
            f"Группа #{result['group_id']}",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
    else:
        members = await db_queries.get_element_members(db, request["element_id"])
        element = await db_queries.get_element(db, request["element_id"])
        spots_left = element["target_size"] - len(members)
        
        await callback.message.edit_text(
            f"✅ <b>Запрос #{join_id} принят!</b>\n\n"
            f"👤 {requester.get('username', 'Пользователь')} добавлен в заявку.\n"
            f"🪑 Осталось мест: {spots_left}",
            reply_markup=manage_element_kb(request["element_id"], request["event_id"]),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("reject_request:"))
async def cb_reject_request(callback: CallbackQuery, db: aiosqlite.Connection, bot: Bot):
    """Кнопка «Отклонить» запрос."""
    join_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Получаем запрос
    request = await db_queries.get_join_request(db, join_id)
    if not request:
        await callback.answer("❌ Запрос не найден", show_alert=True)
        return
    
    # Проверяем, что пользователь — владелец элемента
    if request["element_creator_id"] != user_id:
        await callback.answer("❌ Вы не владелец этой заявки", show_alert=True)
        return
    
    if request["status"] != "pending":
        await callback.answer("❌ Этот запрос уже обработан", show_alert=True)
        return
    
    # Отклоняем запрос
    await db_queries.update_join_request_status(db, join_id, "rejected")
    
    # Получаем данные для уведомления
    event = await db_queries.get_event(db, request["event_id"])
    
    # Логируем
    await db_queries.create_log(
        db,
        "join_request_rejected",
        f"join_id={join_id}, element_id={request['element_id']}, requester_id={request['requester_id']}"
    )
    
    # Уведомляем отправителя запроса
    try:
        await bot.send_message(
            request["requester_id"],
            f"❌ <b>Ваш запрос отклонён</b>\n\n"
            f"📌 Турнир: {event['title']}\n"
            f"Заявка: #{request['element_id']}\n\n"
            f"Вы можете найти другие заявки для присоединения.",
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    await callback.answer("❌ Запрос отклонён", show_alert=True)
    
    # Возвращаемся к списку запросов
    remaining_requests = await db_queries.get_pending_requests_for_element(db, request["element_id"])
    
    await callback.message.edit_text(
        f"❌ <b>Запрос #{join_id} отклонён</b>\n\n"
        f"Осталось запросов: {len(remaining_requests)}",
        reply_markup=manage_element_kb(request["element_id"], request["event_id"]),
        parse_mode="HTML"
    )
