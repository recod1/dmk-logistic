# handlers/admin/messages.py — отправка сообщений администратором
import html
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards.admin_kb import get_admin_main_keyboard
from states.message_states import AdminMessageState
from database.repositories.user_repository import UserRepository
from config.settings import UserRole

router = Router()

TARGET_ALL = "all"
TARGET_DRIVERS = "drivers"
TARGET_ACCOUNTANTS = "accountants"
TARGET_LOGISTICS = "logistics"
TARGET_MECHANICS = "mechanics"
TARGET_USER = "user"


def _get_message_target_inline_keyboard() -> InlineKeyboardBuilder:
    """Инлайн-меню выбора получателей."""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="Всем", callback_data="msg_target_all"),
        types.InlineKeyboardButton(text="Водителям", callback_data="msg_target_drivers"),
    )
    builder.row(
        types.InlineKeyboardButton(text="Бухгалтерам", callback_data="msg_target_accountants"),
        types.InlineKeyboardButton(text="Логистам", callback_data="msg_target_logistics"),
    )
    builder.row(
        types.InlineKeyboardButton(text="Механикам", callback_data="msg_target_mechanics"),
        types.InlineKeyboardButton(text="Пользователю", callback_data="msg_target_user"),
    )
    return builder


def _get_target_users(user_repository: UserRepository, target: str) -> list:
    """Получить список пользователей по типу целевой группы."""
    from config.settings import UserStatus
    if target == TARGET_ALL:
        users = []
        for role in UserRole:
            users.extend(user_repository.get_all_by_role_and_status(role, UserStatus.ACTIVE))
        seen = set()
        result = []
        for u in users:
            if u.tg_id and str(u.tg_id) != "0" and u.tg_id not in seen:
                seen.add(u.tg_id)
                result.append(u)
        return result
    elif target == TARGET_DRIVERS:
        return [u for u in user_repository.get_all_active_drivers() if u.tg_id and str(u.tg_id) != "0"]
    elif target == TARGET_ACCOUNTANTS:
        return [u for u in user_repository.get_all_active_accountants() if u.tg_id and str(u.tg_id) != "0"]
    elif target == TARGET_LOGISTICS:
        return [u for u in user_repository.get_all_active_logistics() if u.tg_id and str(u.tg_id) != "0"]
    elif target == TARGET_MECHANICS:
        return [u for u in user_repository.get_all_active_mechanics() if u.tg_id and str(u.tg_id) != "0"]
    return []


@router.message(F.text == "📨 Сообщение")
async def admin_message_start(message: types.Message, state: FSMContext):
    """Начало отправки сообщения — показ инлайн-меню выбора получателей."""
    await state.set_state(AdminMessageState.target)
    await message.reply(
        "📨 Выберите получателей сообщения:",
        reply_markup=_get_message_target_inline_keyboard().as_markup()
    )


@router.callback_query(F.data.startswith("msg_target_"))
async def admin_message_target_selected(
    callback: types.CallbackQuery,
    state: FSMContext,
    user_repository: UserRepository,
):
    """Обработка выбора группы получателей."""
    target = callback.data.replace("msg_target_", "")
    if target not in (TARGET_ALL, TARGET_DRIVERS, TARGET_ACCOUNTANTS, TARGET_LOGISTICS, TARGET_MECHANICS, TARGET_USER):
        await callback.answer("Неизвестный выбор.")
        return
    await state.update_data(msg_target=target)
    if target == TARGET_USER:
        await state.set_state(AdminMessageState.user_search)
        await callback.message.edit_text(
            "👤 Введите ФИО или часть ФИО пользователя для поиска:",
        )
    else:
        await state.set_state(AdminMessageState.text)
        labels = {
            TARGET_ALL: "всем",
            TARGET_DRIVERS: "водителям",
            TARGET_ACCOUNTANTS: "бухгалтерам",
            TARGET_LOGISTICS: "логистам",
            TARGET_MECHANICS: "механикам",
        }
        await callback.message.edit_text(
            f"📝 Получатели: {labels.get(target, target)}\n\nВведите текст сообщения:",
        )
    await callback.answer()


@router.message(AdminMessageState.user_search, F.text)
async def admin_message_user_search(
    message: types.Message,
    state: FSMContext,
    user_repository: UserRepository,
):
    """Поиск пользователя по ФИО."""
    text = (message.text or "").strip()
    if not text:
        await message.reply("Введите ФИО или часть ФИО:")
        return
    users = user_repository.search_users_by_name_part(text, limit=15)
    if not users:
        await message.reply("❌ Пользователи не найдены. Введите ФИО или часть ФИО:", reply_markup=get_admin_main_keyboard())
        return
    if len(users) == 1:
        u = users[0]
        await state.update_data(msg_user_tg_id=int(u.tg_id), msg_user_name=u.name)
        await state.set_state(AdminMessageState.text)
        await message.reply(
            f"✅ Получатель: {html.escape(u.name)}\n\nВведите текст сообщения:",
            parse_mode="HTML",
        )
        return
    builder = InlineKeyboardBuilder()
    for u in users[:10]:
        if u.tg_id and str(u.tg_id) != "0":
            builder.row(
                types.InlineKeyboardButton(text=u.name, callback_data=f"msg_user_{u.tg_id}"),
            )
    await message.reply("Выберите пользователя:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("msg_user_"))
async def admin_message_user_selected(
    callback: types.CallbackQuery,
    state: FSMContext,
    user_repository: UserRepository,
):
    """Выбор конкретного пользователя из списка."""
    tg_id_str = callback.data.replace("msg_user_", "")
    try:
        tg_id = int(tg_id_str)
    except ValueError:
        await callback.answer("Ошибка.")
        return
    user = user_repository.get_by_tg_id(tg_id)
    if not user:
        await callback.answer("Пользователь не найден.")
        return
    await state.update_data(msg_user_tg_id=tg_id, msg_user_name=user.name)
    await state.set_state(AdminMessageState.text)
    await callback.message.edit_text(
        f"✅ Получатель: {html.escape(user.name)}\n\nВведите текст сообщения:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminMessageState.text, F.text)
async def admin_message_text_received(
    message: types.Message,
    state: FSMContext,
):
    """Получение текста сообщения — показ превью и запрос подтверждения."""
    text = (message.text or "").strip()
    if not text:
        await message.reply("Введите текст сообщения:")
        return
    await state.update_data(msg_text=text)
    await state.set_state(AdminMessageState.confirm)
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="✅ Отправить", callback_data="msg_confirm_send", style="success"),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="msg_confirm_cancel"),
    )
    await message.reply(
        f"📋 Текст сообщения:\n\n{html.escape(text)}\n\nПодтвердите отправку:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "msg_confirm_send")
async def admin_message_confirm_send(
    callback: types.CallbackQuery,
    state: FSMContext,
    user_repository: UserRepository,
):
    """Подтверждение и отправка сообщения."""
    data = await state.get_data()
    msg_text = data.get("msg_text", "").strip()
    msg_target = data.get("msg_target")
    msg_user_tg_id = data.get("msg_user_tg_id")
    await state.clear()
    if not msg_text:
        await callback.answer("Текст сообщения не найден.")
        return
    recipients = []
    if msg_target == TARGET_USER and msg_user_tg_id:
        user = user_repository.get_by_tg_id(msg_user_tg_id)
        if user:
            recipients = [user]
    else:
        recipients = _get_target_users(user_repository, msg_target or "")
    if not recipients:
        await callback.message.edit_text(
            "❌ Нет получателей для отправки сообщения.",
        )
        await callback.answer()
        return
    from core.bot import create_bot
    bot = create_bot()
    sent = 0
    failed_list: list[tuple[str, str]] = []
    for u in recipients:
        try:
            await bot.send_message(int(u.tg_id), msg_text)
            sent += 1
        except Exception as e:
            failed_list.append((u.name or f"ID {u.tg_id}", str(e)))
    result_text = f"✅ Сообщение отправлено: {sent} получателей."
    if failed_list:
        result_text += "\n\n⚠️ Не доставлено:\n" + "\n".join(
            f"• {html.escape(name)}: {html.escape(err)}" for name, err in failed_list
        )
    await callback.message.edit_text(result_text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "msg_confirm_cancel")
async def admin_message_confirm_cancel(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    """Отмена отправки сообщения."""
    await state.clear()
    await callback.message.edit_text("❌ Отправка отменена.")
    await callback.message.answer("Главное меню:", reply_markup=get_admin_main_keyboard())
    await callback.answer()
