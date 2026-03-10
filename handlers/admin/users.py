import html
from urllib.parse import quote
from aiogram import Router, types, F
from utils.telegram_helpers import copy_link_fio
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.admin_kb import (
    get_users_keyboard,
    get_user_role_keyboard,
    get_admin_main_keyboard,
    get_edit_user_param_keyboard,
    get_edit_user_role_keyboard,
    get_edit_user_status_keyboard,
)
from states.user_states import RegisterState, BlockedState, EditUserState, DeleteUserState
from database.repositories.user_repository import UserRepository
from database.repositories.route_repository import RouteRepository
from config.settings import UserRole, UserStatus

router = Router()

ROLE_LABELS = {
    UserRole.ADMIN: "Администратор",
    UserRole.DRIVER: "Водитель",
    UserRole.LOGISTIC: "Логист",
    UserRole.ACCOUNTANT: "Бухгалтер",
    UserRole.MECHANIC: "Механик",
}
STATUS_LABELS = {
    UserStatus.ACTIVE: "Активен",
    UserStatus.INVITE: "Не подтверждён",
    UserStatus.BLOCKED: "Заблокирован",
}


def _format_user_line(user):
    return f"ID: {user.tg_id or '-'} | ФИО: {user.name} | 📞 {user.phone or '-'}"


def _format_user_line_html(user):
    """Строка пользователя с копируемым по клику ФИО (для вывода с parse_mode=HTML)."""
    name = (user.name or "").strip() or "—"
    copy_fio = f'<a href="tg://copy?text={quote(name)}"><code>{html.escape(name)}</code></a>'
    return f"ID: {user.tg_id or '-'} | ФИО: {copy_fio} | 📞 {html.escape(user.phone or '-')}"


@router.message(F.text == "🤵🏼‍♂️ Пользователи")
async def menu_users(message: types.Message):
    await message.reply("Раздел пользователи", reply_markup=get_users_keyboard())

@router.message(F.text == "👩‍👩‍👦‍👦 Все пользователи")
async def all_users(message: types.Message, user_repository: UserRepository):
    # Получаем всех пользователей по ролям
    all_admins = user_repository.get_all_by_role_and_status(UserRole.ADMIN, UserStatus.ACTIVE)
    all_drivers = user_repository.get_all_by_role_and_status(UserRole.DRIVER, UserStatus.ACTIVE)
    all_logistics = user_repository.get_all_by_role_and_status(UserRole.LOGISTIC, UserStatus.ACTIVE)
    all_accountants = user_repository.get_all_by_role_and_status(UserRole.ACCOUNTANT, UserStatus.ACTIVE)
    all_mechanics = user_repository.get_all_by_role_and_status(UserRole.MECHANIC, UserStatus.ACTIVE)
    
    all_invite_users = user_repository.get_all_by_role_and_status(UserRole.DRIVER, UserStatus.INVITE)

    lines = ["📊 Все пользователи\n"]

    lines.append("👑 Администраторы:")
    if all_admins:
        lines.extend([_format_user_line_html(u) for u in all_admins])
    else:
        lines.append("  — нет")

    lines.append("\n🚚 Водители:")
    if all_drivers:
        lines.extend([_format_user_line_html(u) for u in all_drivers])
    else:
        lines.append("  — нет")

    lines.append("\n📋 Логисты:")
    if all_logistics:
        lines.extend([_format_user_line_html(u) for u in all_logistics])
    else:
        lines.append("  — нет")

    lines.append("\n💰 Бухгалтеры:")
    if all_accountants:
        lines.extend([_format_user_line_html(u) for u in all_accountants])
    else:
        lines.append("  — нет")

    lines.append("\n🔧 Механики:")
    if all_mechanics:
        lines.extend([_format_user_line_html(u) for u in all_mechanics])
    else:
        lines.append("  — нет")

    lines.append("\n⏳ Не подтвержденные водители:")
    if all_invite_users:
        lines.extend([_format_user_line_html(u) for u in all_invite_users])
    else:
        lines.append("  — нет")

    all_user_text = "\n".join(lines)

    await message.reply(all_user_text, reply_markup=get_users_keyboard(), parse_mode="HTML")


@router.message(F.text == "🚫 Заблокированные")
async def blocked_users(message: types.Message, user_repository: UserRepository):
    users = user_repository.get_all_blocked()
    if not users:
        await message.reply("📭 Нет заблокированных пользователей.", reply_markup=get_users_keyboard())
        return
    lines = ["🚫 Заблокированные пользователи\n"]
    for u in users:
        lines.append(_format_user_line_html(u))
    await message.reply("\n".join(lines), reply_markup=get_users_keyboard(), parse_mode="HTML")


@router.message(F.text == "➕ Добавить пользователя")
async def add_user(message: types.Message, state: FSMContext):
    await state.set_state(RegisterState.name)
    await message.reply("Введите ФИО пользователя:", reply_markup=get_users_keyboard())

@router.message(F.text == "✏️ Изменить пользователя")
async def edit_user_start(message: types.Message, state: FSMContext):
    await state.set_state(EditUserState.tg_id)
    await message.reply(
        "Введите ID пользователя (Telegram ID).\n\nID можно посмотреть в разделе «👩‍👩‍👦‍👦 Все пользователи».",
        reply_markup=get_users_keyboard(),
    )


@router.message(EditUserState.tg_id)
async def edit_user_tg_id(message: types.Message, state: FSMContext, user_repository: UserRepository):
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.reply("Неверный формат ID. Введите число (Telegram ID пользователя).", reply_markup=get_users_keyboard())
        return
    user = user_repository.get_by_tg_id(tg_id)
    if not user:
        await state.clear()
        await message.reply("Пользователь с таким ID не найден.", reply_markup=get_users_keyboard())
        return
    await state.update_data(edit_user_tg_id=tg_id, edit_user_name=user.name, edit_user_phone=user.phone or "")
    await state.set_state(EditUserState.new_value)
    await state.update_data(edit_user_param=None)
    text = (
        f"👤 Пользователь: {copy_link_fio(user.name)}\n"
        f"ID: {user.tg_id}\n"
        f"📞 Телефон: {html.escape(user.phone or '—')}\n"
        f"📊 Статус: {STATUS_LABELS.get(user.status, user.status)}\n"
        f"🎯 Роль: {ROLE_LABELS.get(user.role, user.role)}\n\n"
        "Выберите параметр для изменения:"
    )
    await message.reply(text, reply_markup=get_edit_user_param_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "edit_user_name")
async def edit_user_choose_name(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(edit_user_param="name")
    await state.set_state(EditUserState.new_value)
    await callback.message.edit_text("Введите новое ФИО пользователя:")
    await callback.answer()


@router.callback_query(F.data == "edit_user_phone")
async def edit_user_choose_phone(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(edit_user_param="phone")
    await state.set_state(EditUserState.new_value)
    await callback.message.edit_text("Введите новый номер телефона:")
    await callback.answer()


@router.callback_query(F.data == "edit_user_status")
async def edit_user_choose_status(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(edit_user_param="status")
    await callback.message.edit_text("Выберите новый статус:", reply_markup=get_edit_user_status_keyboard())
    await callback.answer()


@router.callback_query(F.data == "edit_user_role")
async def edit_user_choose_role(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(edit_user_param="role")
    await callback.message.edit_text("Выберите новую роль:", reply_markup=get_edit_user_role_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_status_"))
async def edit_user_apply_status(
    callback: types.CallbackQuery, state: FSMContext, user_repository: UserRepository
):
    status_key = callback.data.replace("edit_status_", "")
    status_map = {"active": UserStatus.ACTIVE, "invite": UserStatus.INVITE, "blocked": UserStatus.BLOCKED}
    status = status_map.get(status_key)
    if not status:
        await callback.answer()
        return
    data = await state.get_data()
    tg_id = data.get("edit_user_tg_id")
    if tg_id is None:
        await callback.message.answer("Сессия истекла. Начните изменение пользователя заново.", reply_markup=get_users_keyboard())
        await state.clear()
        await callback.answer()
        return
    ok = user_repository.update_status(tg_id, status)
    await state.clear()
    if ok:
        await callback.message.edit_text(f"✅ Статус пользователя (ID: {tg_id}) изменён на: {STATUS_LABELS.get(status, status)}")
    else:
        await callback.message.edit_text(f"❌ Не удалось изменить статус пользователя ID: {tg_id}")
    await callback.answer()


@router.callback_query(F.data.startswith("edit_role_"))
async def edit_user_apply_role(
    callback: types.CallbackQuery, state: FSMContext, user_repository: UserRepository
):
    role_key = callback.data.replace("edit_role_", "")
    role_map = {
        "driver": UserRole.DRIVER,
        "admin": UserRole.ADMIN,
        "logistic": UserRole.LOGISTIC,
        "accountant": UserRole.ACCOUNTANT,
        "mechanic": UserRole.MECHANIC,
    }
    role = role_map.get(role_key)
    if not role:
        await callback.answer()
        return
    data = await state.get_data()
    tg_id = data.get("edit_user_tg_id")
    if tg_id is None:
        await callback.message.answer("Сессия истекла. Начните изменение пользователя заново.", reply_markup=get_users_keyboard())
        await state.clear()
        await callback.answer()
        return
    ok = user_repository.update_role(tg_id, role)
    await state.clear()
    if ok:
        await callback.message.edit_text(f"✅ Роль пользователя (ID: {tg_id}) изменена на: {ROLE_LABELS.get(role, role)}")
    else:
        await callback.message.edit_text(f"❌ Не удалось изменить роль пользователя ID: {tg_id}")
    await callback.answer()


@router.message(EditUserState.new_value, F.text)
async def edit_user_new_value(
    message: types.Message, state: FSMContext, user_repository: UserRepository
):
    data = await state.get_data()
    param = data.get("edit_user_param")
    tg_id = data.get("edit_user_tg_id")
    if tg_id is None or not param:
        await state.clear()
        await message.reply("Выберите параметр в меню выше или начните изменение заново.", reply_markup=get_users_keyboard())
        return
    value = message.text.strip()
    if param == "name":
        ok = user_repository.update_name(tg_id, value)
        if ok:
            await message.reply(f"✅ ФИО пользователя (ID: {tg_id}) изменено на: {value}", reply_markup=get_users_keyboard())
        else:
            await message.reply(f"❌ Не удалось изменить ФИО пользователя ID: {tg_id}", reply_markup=get_users_keyboard())
    elif param == "phone":
        ok = user_repository.update_phone(tg_id, value)
        if ok:
            await message.reply(f"✅ Телефон пользователя (ID: {tg_id}) изменён на: {value}", reply_markup=get_users_keyboard())
        else:
            await message.reply(f"❌ Не удалось изменить телефон пользователя ID: {tg_id}", reply_markup=get_users_keyboard())
    else:
        await message.reply("Выберите параметр в инлайн-меню (ФИО или Телефон).", reply_markup=get_users_keyboard())
    await state.clear()


@router.message(F.text == "❌ Заблокировать пользователя")
async def block_user(message: types.Message, state: FSMContext):
    await state.set_state(BlockedState.tg_id)
    await message.reply("Введите ID пользователя:", reply_markup=get_users_keyboard())

@router.message(BlockedState.tg_id)
async def block_user_tg_id(message: types.Message, state: FSMContext, user_repository: UserRepository):
    await state.update_data(tg_id=message.text)
    data = await state.get_data()
    
    try:
        tg_id = int(data["tg_id"])
        success = user_repository.block_user(tg_id)
        
        if success:
            await message.answer(f"Пользователь с ID {tg_id} заблокирован")
        else:
            await message.answer(f"Пользователь с ID {tg_id} не найден")
        await state.clear()
    except ValueError:
        await state.clear()
        await message.answer("Неверный формат ID")


# --- Удаление пользователя ---

def _delete_user_confirm_keyboard(tg_id: int, user_name: str = None, user_phone: str = None):
    """Создает клавиатуру подтверждения удаления. Использует комбинацию tg_id+name+phone для уникальности при tg_id=0."""
    # Для пользователей с tg_id=0 используем комбинацию полей для уникальности callback_data
    if tg_id == 0 and user_name and user_phone:
        # Используем хеш от комбинации полей для создания уникального идентификатора
        import hashlib
        unique_key = hashlib.md5(f"{tg_id}_{user_name}_{user_phone}".encode()).hexdigest()[:8]
        callback_data = f"confirm_delete_user_unique_{unique_key}"
    else:
        callback_data = f"confirm_delete_user_{tg_id}"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="✅ Подтвердить удаление", callback_data=callback_data),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_user"),
    )
    return builder.as_markup()


def _build_delete_confirm_text(user, routes: list) -> str:
    parts = [
        "🗑 Удаление пользователя",
        f"👤 ФИО: {copy_link_fio(user.name)}",
        f"ID: {user.tg_id}",
        f"📞 {html.escape(user.phone or '—')}",
        "",
    ]
    if routes:
        route_ids = ", ".join(html.escape(r.id) for r in routes)
        parts.append(f"⚠️ У пользователя есть назначенные рейсы: {route_ids}")
        parts.append("После удаления ФИО водителя в этих рейсах будет отображаться как «Неизвестно».")
        parts.append("")
        parts.append("Удалить пользователя?")
    else:
        parts.append("Назначенных рейсов нет. Удалить пользователя?")
    return "\n".join(parts)


@router.message(F.text == "🗑 Удалить пользователя")
async def delete_user_start(message: types.Message, state: FSMContext):
    await state.set_state(DeleteUserState.method)
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="По ID (Telegram ID)", callback_data="delete_user_method_id"),
        types.InlineKeyboardButton(text="По ФИО", callback_data="delete_user_method_fio"),
    )
    await message.reply(
        "Удалить пользователя по ID или по ФИО?",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "delete_user_method_id")
async def delete_user_by_id_ask(
    callback: types.CallbackQuery, state: FSMContext
):
    await state.update_data(delete_method="by_id")
    await state.set_state(DeleteUserState.input_value)
    await callback.message.edit_text("Введите Telegram ID пользователя (число):")
    await callback.answer()


@router.callback_query(F.data == "delete_user_method_fio")
async def delete_user_by_fio_ask(
    callback: types.CallbackQuery, state: FSMContext
):
    await state.update_data(delete_method="by_fio")
    await state.set_state(DeleteUserState.input_value)
    await callback.message.edit_text("Введите ФИО пользователя:")
    await callback.answer()


@router.message(DeleteUserState.input_value, F.text)
async def delete_user_input(
    message: types.Message,
    state: FSMContext,
    user_repository: UserRepository,
    route_repository: RouteRepository,
):
    data = await state.get_data()
    method = data.get("delete_method")
    text = message.text.strip()
    if not text:
        await message.reply("Введите ID или ФИО.", reply_markup=get_users_keyboard())
        return

    if method == "by_id":
        try:
            tg_id = int(text)
        except ValueError:
            await message.reply("Неверный формат ID. Введите число.", reply_markup=get_users_keyboard())
            await state.clear()
            return
        user = user_repository.get_by_tg_id(tg_id)
        if not user:
            await state.clear()
            await message.reply(f"Пользователь с ID {tg_id} не найден.", reply_markup=get_users_keyboard())
            return
        # Сохраняем выбранного пользователя в state для точного удаления
        await state.update_data(
            delete_selected_user_tg_id=user.tg_id,
            delete_selected_user_name=user.name,
            delete_selected_user_phone=user.phone or "",
        )
        routes = route_repository.get_routes_by_driver(tg_id)
        msg = _build_delete_confirm_text(user, routes)
        await message.reply(
            msg,
            reply_markup=_delete_user_confirm_keyboard(tg_id, user.name, user.phone or ""),
            parse_mode="HTML",
        )
        await state.clear()
        return

    # by_fio
    users = user_repository.check_name_user(text)
    if not users:
        await state.clear()
        await message.reply(f"Пользователь с ФИО «{text}» не найден.", reply_markup=get_users_keyboard())
        return
    if len(users) == 1:
        user = users[0]
        # Сохраняем выбранного пользователя в state для точного удаления
        await state.update_data(
            delete_selected_user_tg_id=user.tg_id,
            delete_selected_user_name=user.name,
            delete_selected_user_phone=user.phone or "",
        )
        tg_id = int(user.tg_id) if user.tg_id and user.tg_id != "0" else 0
        routes = route_repository.get_routes_by_driver(tg_id)
        msg = _build_delete_confirm_text(user, routes)
        await message.reply(
            msg,
            reply_markup=_delete_user_confirm_keyboard(tg_id, user.name, user.phone or ""),
            parse_mode="HTML",
        )
        await state.clear()
        return
    # Несколько пользователей с одинаковым ФИО
    # Сохраняем список пользователей в state для последующего извлечения по индексу
    # (используем индекс вместо tg_id, т.к. у нескольких пользователей может быть tg_id = "0")
    await state.update_data(delete_users_list=users)
    builder = InlineKeyboardBuilder()
    for idx, u in enumerate(users):
        label = f"ID: {u.tg_id} | {u.name} | {ROLE_LABELS.get(u.role, u.role)}"
        if len(label) > 60:
            label = f"ID: {u.tg_id} | {u.name}"
        # Используем индекс в списке для уникальности callback_data
        builder.row(
            types.InlineKeyboardButton(text=label, callback_data=f"delete_user_choose_idx_{idx}")
        )
    await message.reply(
        "Найдено несколько пользователей с таким ФИО. Выберите, кого удалить:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("delete_user_choose_"))
async def delete_user_choose_one(
    callback: types.CallbackQuery,
    state: FSMContext,
    user_repository: UserRepository,
    route_repository: RouteRepository,
):
    callback_data = callback.data
    # Проверяем, используется ли индекс (новый формат) или tg_id (старый формат для совместимости)
    if callback_data.startswith("delete_user_choose_idx_"):
        # Новый формат: используем индекс из сохраненного списка
        idx_str = callback_data.replace("delete_user_choose_idx_", "")
        try:
            idx = int(idx_str)
            data = await state.get_data()
            users_list = data.get("delete_users_list")
            if not users_list or idx < 0 or idx >= len(users_list):
                await callback.message.edit_text("❌ Пользователь не найден. Начните удаление заново.")
                await state.clear()
                await callback.answer()
                return
            user = users_list[idx]
            await state.clear()
        except (ValueError, IndexError, TypeError):
            await callback.message.edit_text("❌ Ошибка при выборе пользователя. Начните удаление заново.")
            await state.clear()
            await callback.answer()
            return
    else:
        # Старый формат: используем tg_id (для совместимости с другими местами, где может использоваться этот callback)
        tg_id = int(callback_data.replace("delete_user_choose_", ""))
        user = user_repository.get_by_tg_id(tg_id)
        if not user:
            await callback.message.edit_text("Пользователь не найден.")
            await callback.answer()
            return
    
    # Сохраняем выбранного пользователя в state для точного удаления
    await state.update_data(
        delete_selected_user_tg_id=user.tg_id,
        delete_selected_user_name=user.name,
        delete_selected_user_phone=user.phone or "",
    )
    
    # Получаем tg_id для дальнейших операций
    tg_id = int(user.tg_id) if user.tg_id and user.tg_id != "0" else 0
    routes = route_repository.get_routes_by_driver(tg_id)
    msg = _build_delete_confirm_text(user, routes)
    await callback.message.edit_text(
        msg,
        reply_markup=_delete_user_confirm_keyboard(tg_id, user.name, user.phone or ""),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_user_"))
async def delete_user_confirm(
    callback: types.CallbackQuery,
    state: FSMContext,
    user_repository: UserRepository,
    route_repository: RouteRepository,
):
    callback_data = callback.data
    
    # Проверяем формат callback_data
    if callback_data.startswith("confirm_delete_user_unique_"):
        # Используем сохраненные данные пользователя из state
        data = await state.get_data()
        user_tg_id = data.get("delete_selected_user_tg_id")
        user_name = data.get("delete_selected_user_name")
        user_phone = data.get("delete_selected_user_phone")
        
        if not user_tg_id or not user_name:
            await callback.message.edit_text("❌ Сессия истекла. Начните удаление заново.")
            await state.clear()
            await callback.answer()
            return
        
        # Удаляем пользователя по точному совпадению всех полей для гарантии удаления правильного пользователя
        tg_id_for_delete = int(user_tg_id) if user_tg_id != "0" else 0
        # Для пользователей с tg_id=0 удаляем по комбинации tg_id + name + phone
        if tg_id_for_delete == 0:
            ok = user_repository.delete_user_by_fields(user_tg_id, user_name, user_phone or "")
        else:
            ok = user_repository.delete_user(tg_id_for_delete)
    else:
        # Старый формат: используем только tg_id
        tg_id = int(callback_data.replace("confirm_delete_user_", ""))
        ok = user_repository.delete_user(tg_id)
        tg_id_for_delete = tg_id
    
    await state.clear()
    
    if ok:
        routes = route_repository.get_routes_by_driver(tg_id_for_delete)
        route_ids = ", ".join(r.id for r in routes) if routes else ""
        if route_ids:
            await callback.message.edit_text(
                f"✅ Пользователь удалён. В рейсах {route_ids} ФИО водителя будет отображаться как «Неизвестно»."
            )
        else:
            await callback.message.edit_text(f"✅ Пользователь удалён.")
    else:
        await callback.message.edit_text(f"❌ Не удалось удалить пользователя.")
    await callback.answer()


@router.callback_query(F.data == "cancel_delete_user")
async def delete_user_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Удаление отменено.")
    await callback.answer()


@router.message(RegisterState.name)
async def register_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(RegisterState.phone)
    await message.answer("Введите номер телефона")

@router.message(RegisterState.phone)
async def register_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(RegisterState.role)
    await message.answer("Выберите роль пользователя", reply_markup=get_user_role_keyboard())

@router.callback_query(F.data == "change_driver")
async def change_driver(callback: types.CallbackQuery, state: FSMContext, user_repository: UserRepository):
    data = await state.get_data()
    user = user_repository.create(data["name"], data["phone"], UserRole.DRIVER)
    
    await callback.message.answer(
        f"✅ Пользователь создан\n\n"
        f"👤 ФИО: {copy_link_fio(data['name'])}\n"
        f"📞 Телефон: {html.escape(data['phone'])}\n"
        f"🎯 Должность: Водитель 🚚",
        parse_mode="HTML",
    )
    await state.clear()

@router.callback_query(F.data == "change_admin")
async def change_admin(callback: types.CallbackQuery, state: FSMContext, user_repository: UserRepository):
    data = await state.get_data()
    user = user_repository.create(data["name"], data["phone"], UserRole.ADMIN)
    
    await callback.message.answer(
        f"✅ Пользователь создан\n\n"
        f"👤 ФИО: {copy_link_fio(data['name'])}\n"
        f"📞 Телефон: {html.escape(data['phone'])}\n"
        f"🎯 Должность: Администратор 👑",
        parse_mode="HTML",
    )
    await state.clear()

@router.callback_query(F.data == "change_logistic")
async def change_logistic(callback: types.CallbackQuery, state: FSMContext, user_repository: UserRepository):
    data = await state.get_data()
    user = user_repository.create(data["name"], data["phone"], UserRole.LOGISTIC)
    
    await callback.message.answer(
        f"✅ Пользователь создан\n\n"
        f"👤 ФИО: {copy_link_fio(data['name'])}\n"
        f"📞 Телефон: {html.escape(data['phone'])}\n"
        f"🎯 Должность: Логист 📋",
        parse_mode="HTML",
    )
    await state.clear()

@router.callback_query(F.data == "change_accountant")
async def change_accountant(callback: types.CallbackQuery, state: FSMContext, user_repository: UserRepository):
    data = await state.get_data()
    user = user_repository.create(data["name"], data["phone"], UserRole.ACCOUNTANT)
    
    await callback.message.answer(
        f"✅ Пользователь создан\n\n"
        f"👤 ФИО: {copy_link_fio(data['name'])}\n"
        f"📞 Телефон: {html.escape(data['phone'])}\n"
        f"🎯 Должность: Бухгалтер 💰",
        parse_mode="HTML",
    )
    await state.clear()

@router.callback_query(F.data == "change_mechanic")
async def change_mechanic(callback: types.CallbackQuery, state: FSMContext, user_repository: UserRepository):
    data = await state.get_data()
    user = user_repository.create(data["name"], data["phone"], UserRole.MECHANIC)
    
    await callback.message.answer(
        f"✅ Пользователь создан\n\n"
        f"👤 ФИО: {copy_link_fio(data['name'])}\n"
        f"📞 Телефон: {html.escape(data['phone'])}\n"
        f"🎯 Должность: Механик 🔧",
        parse_mode="HTML",
    )
    await state.clear()