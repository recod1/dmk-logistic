import html
from typing import List
from aiogram import Bot, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config.settings import settings
from utils.telegram_helpers import copy_link_fio, copy_link_text, format_point_time_display

# Импортируем здесь только типы, а не сами классы
from database.models.repair import Repair
from database.models.route import Route
from database.models.user import User
from database.models.salary import Salary
from database.repositories.route_repository import RouteRepository
from config.settings import UserRole

from keyboards.driver_kb import (
    get_driver_repairs_keyboard,
    get_ticket_confirm_driver_keyboard,
    get_ticket_proc_repair_driver_keyboard,
    get_ticket_conf_repair_driver_keyboard,
    get_ticket_success_repair_driver_keyboard,
    get_driver_main_keyboard
)

class NotificationService:
    """Сервис для отправки уведомлений"""
    
    def __init__(self, user_repository):
        self.user_repository = user_repository
        self.bot = Bot(token=settings.TG_TOKEN)

    def _format_route_info_for_driver(self, route) -> str:
        """Блок информации о рейсе для уведомления водителю (ТС, прицеп, температура, контакты, N регистрации)."""
        number_auto = (route.number_auto or "").strip()
        trailer_number = (getattr(route, 'trailer_number', None) or "").strip()
        temperature = (route.temperature or "").strip()
        dispatcher_contacts = (route.dispatcher_contacts or "").strip()
        registration_number = (getattr(route, 'registration_number', None) or "").strip()
        lines = [
            f"📋 N рейса: {route.id}",
            f"🚚 ТС: {copy_link_text(number_auto or '—')}",
            f"🛞 Прицеп: {copy_link_text(trailer_number or '—')}",
            f"🌡 Температура: {temperature or '—'}",
            f"☎ Контакты диспетчера: {dispatcher_contacts or '—'}",
            f"📋 N регистрации: {registration_number or '—'}",
        ]
        return "\n".join(lines)

    async def notify_driver_new_route(self, route, route_repository: RouteRepository):
        """Уведомление водителю о новом рейсе. При наличии активного рейса — одно короткое сообщение без дублирования."""
        try:
            all_routes = route_repository.get_all()
            driver_active_routes = [r for r in all_routes if r.tg_id == route.tg_id and r.status == "process"]
            if driver_active_routes:
                text = (
                    f"📋 У вас новый рейс (N рейса: {route.id}).\n\n"
                    f"⚠️ У вас уже есть активный рейс: {driver_active_routes[0].id}. "
                    f"Новый рейс будет доступен после завершения текущего.\n\n"
                    "Чтобы посмотреть новый рейс, нажмите «🚚 Рейс»."
                )
                await self.bot.send_message(int(route.tg_id), text, parse_mode="HTML")
                return
            text = "📋 У вас новый рейс\n\n"
            text += self._format_route_info_for_driver(route)
            text += "\n\n"
            points_ids = (route.points or "").split(",") if route.points != "0" else []
            if points_ids and points_ids[0] != "0":
                text += "\n📍 Точки:\n"
                for point_id_str in points_ids:
                    if point_id_str == "0":
                        continue
                    try:
                        point = route_repository.get_point_by_id(int(point_id_str))
                        if point:
                            type_emoji = "📦" if point.type_point == "loading" else "📤"
                            type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
                            text += f"  {type_emoji} {type_text}: {point.place_point} ({point.date_point})\n"
                    except (ValueError, TypeError):
                        continue
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="✅ Принять рейс",
                callback_data=f"accept_route_{route.id}"
            ))
            await self.bot.send_message(int(route.tg_id), text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка при отправке уведомления водителю {route.tg_id}: {e}")
    
    async def notify_about_new_repair(
        self, 
        ticket_id: int, 
        number_auto: str, 
        malfunction: str,
        driver_id: int
    ):
        """Уведомить администраторов и механиков о новой заявке на ремонт"""
        # Получаем всех, кто должен получить уведомление
        admins = self.user_repository.get_all_active_admins()
        mechanics = self.user_repository.get_all_active_mechanics()
        recipients = admins + mechanics
        
        driver = self.user_repository.get_by_tg_id(driver_id)
        driver_name = driver.name if driver else "Неизвестно"
        driver_phone = driver.phone if driver else "Неизвестно"
        text = (
            "🆕 Новая заявка на ремонт\n\n"
            f"#️⃣Номер заявки: {ticket_id}\n"
            f"🚛Номер ТС: {html.escape(number_auto)}\n"
            f"📝Описание неисправности: {html.escape(malfunction)}\n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"📞 Телефон: {html.escape(driver_phone)}"
        )
        for recipient in recipients:
            try:
                await self.bot.send_message(
                    int(recipient.tg_id),
                    text,
                    reply_markup=self._get_ticket_repair_keyboard(ticket_id),
                    parse_mode="HTML",
                )
            except Exception as e:
                print(f"Не удалось отправить уведомление пользователю {recipient.tg_id}: {e}")
    
    def _get_ticket_repair_keyboard(self, ticket_id: int):
        """Создает клавиатуру для обработки конкретной заявки"""
        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(
            text="🔧 Обработать", 
            callback_data=f"ticket_repair_{ticket_id}"
        ))
        return builder.as_markup()
    
    def _get_ticket_success_repair_keyboard(self, ticket_id: int):
        """Создает клавиатуру для подтверждения окончания ремонта администратором"""
        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(
            text="✅ Подтвердить окончание", 
            callback_data=f"ticket_success_admin_{ticket_id}"
        ))
        return builder.as_markup()
    
    async def notify_about_confirmed_repair(self, repair: Repair):
        """Уведомить администраторов и механиков о подтвержденной заявке"""
        admins = self.user_repository.get_all_active_admins()
        mechanics = self.user_repository.get_all_active_mechanics()
        recipients = admins + mechanics
        
        driver = self.user_repository.get_by_tg_id(int(repair.tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        driver_phone = driver.phone if driver else "Неизвестно"
        admin_text = (
            "✅ Заявка на ремонт подтверждена водителем\n\n"
            f"#️⃣ Номер заявки: {repair.id_ticket}\n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"📞 Телефон водителя: {html.escape(driver_phone)}\n"
            f"🚛 Номер ТС: {html.escape(repair.number_auto)}\n"
            f"📝 Описание неисправности: {html.escape(repair.malfunction)}\n"
            f"📅 Дата ремонта: {html.escape(repair.date_repair if repair.date_repair != '0' else 'не указана')}\n"
            f"🗺 Место ремонта: {html.escape(repair.place_repair if repair.place_repair != '0' else 'не указано')}\n"
            f"🗒 Комментарий: {html.escape(repair.comment_repair if repair.comment_repair != '0' else 'нет')}\n\n"
            "📊 Статус: 📨 Ожидает выезда на ремонт"
        )
        for recipient in recipients:
            try:
                await self.bot.send_message(int(recipient.tg_id), admin_text, parse_mode="HTML")
            except Exception as e:
                print(f"Ошибка отправки уведомления пользователю {recipient.tg_id}: {e}")
    
    async def notify_about_departure_for_repair(self, repair: Repair):
        """Уведомить администраторов и механиков о выезде на ремонт"""
        admins = self.user_repository.get_all_active_admins()
        mechanics = self.user_repository.get_all_active_mechanics()
        recipients = admins + mechanics
        
        driver = self.user_repository.get_by_tg_id(int(repair.tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        admin_text = (
            "🚗 Водитель выехал на ремонт\n\n"
            f"#️⃣ Номер заявки: {repair.id_ticket}\n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {html.escape(repair.number_auto)}\n"
            f"📝 Описание неисправности: {html.escape(repair.malfunction)}\n"
            f"📅 Дата ремонта: {html.escape(repair.date_repair if repair.date_repair != '0' else 'не указана')}\n"
            f"🗺 Место ремонта: {html.escape(repair.place_repair if repair.place_repair != '0' else 'не указано')}\n"
            f"🗒 Комментарий: {html.escape(repair.comment_repair if repair.comment_repair != '0' else 'нет')}\n\n"
            "📊 Статус: 🛻 Выехал на ремонт"
        )
        for recipient in recipients:
            try:
                await self.bot.send_message(int(recipient.tg_id), admin_text, parse_mode="HTML")
            except Exception as e:
                print(f"Ошибка отправки уведомления пользователю {recipient.tg_id}: {e}")
    
    async def notify_about_completed_repair(self, repair: Repair):
        """Уведомить администраторов и механиков об окончании ремонта"""
        admins = self.user_repository.get_all_active_admins()
        mechanics = self.user_repository.get_all_active_mechanics()
        recipients = admins + mechanics
        
        driver = self.user_repository.get_by_tg_id(int(repair.tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        admin_text = (
            "🛠 Водитель завершил ремонт\n\n"
            f"#️⃣ Номер заявки: {repair.id_ticket}\n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {html.escape(repair.number_auto)}\n"
            f"📝 Описание неисправности: {html.escape(repair.malfunction)}\n"
            f"📅 Дата ремонта: {html.escape(repair.date_repair if repair.date_repair != '0' else 'не указана')}\n"
            f"🗺 Место ремонта: {html.escape(repair.place_repair if repair.place_repair != '0' else 'не указано')}\n"
            f"🗒 Комментарий: {html.escape(repair.comment_repair if repair.comment_repair != '0' else 'нет')}\n\n"
            "📊 Статус: 🛠 Отремонтирована\n\n"
            "Подтвердите окончание ремонта:"
        )
        for recipient in recipients:
            try:
                await self.bot.send_message(
                    int(recipient.tg_id),
                    admin_text,
                    parse_mode="HTML",
                    reply_markup=self._get_ticket_success_repair_keyboard(repair.id_ticket)
                )
            except Exception as e:
                print(f"Ошибка отправки уведомления пользователю {recipient.tg_id}: {e}")

    # Алиасы для совместимости со старыми вызовами из handlers/driver/repairs.py
    async def notify_admins_about_departure_for_repair(self, repair: Repair):
        """Совместимость: старое имя метода -> новое notify_about_departure_for_repair"""
        await self.notify_about_departure_for_repair(repair)

    async def notify_admins_about_completed_repair(self, repair: Repair):
        """Совместимость: старое имя метода -> новое notify_about_completed_repair"""
        await self.notify_about_completed_repair(repair)

    async def notify_about_status_point(
        self,
        route_id,
        point_status,
        text,
        point_time=None,
        point_type=None,
        point_address=None,
        point_date=None,
        point_coords=None,
        point_odometer=None,
    ):
        """Уведомить администраторов и логистов о статусе рейса. Структура: N рейса, водитель, статус (копирование по клику)."""
        admins = self.user_repository.get_all_active_admins()
        logistics = self.user_repository.get_all_active_logistics()
        recipients = admins + logistics

        driver_name = "Неизвестно"
        number_auto = ""
        temperature = ""
        dispatcher_contacts = ""
        route = None
        try:
            route_repo = RouteRepository()
            route = route_repo.get_route_info(str(route_id))
            if route:
                number_auto = route.number_auto or ""
                temperature = route.temperature or ""
                dispatcher_contacts = route.dispatcher_contacts or ""
                driver = self.user_repository.get_by_tg_id(int(route.tg_id))
                if driver and driver.name:
                    driver_name = driver.name
        except Exception as e:
            print(f"Ошибка при получении водителя для маршрута {route_id}: {e}")

        status_info = {
            "process": ("🚗", "Выехал на точку"),
            "registration": ("📝", "Зарегистрировался"),
            "load": ("🚪", "Поставил на ворота"),
            "docs": ("📋", "Забрал документы"),
            "success": ("🏁", "Выехал с точки"),
            "completed": ("✅", "Завершил рейс")
        }
        emoji, status_text = status_info.get(point_status, ("❓", "Неизвестно"))

        from html import escape
        from urllib.parse import quote
        def _copy_link(text: str) -> str:
            safe = (text or "").strip() or "—"
            return f'<a href="tg://copy?text={quote(safe)}"><code>{escape(safe)}</code></a>'
        registration_number = (getattr(route, 'registration_number', None) or "").strip() if route else ""
        trailer_number = (getattr(route, 'trailer_number', None) or "").strip() if route else ""

        admin_text = (
            f"<b>N рейса:</b> {_copy_link(str(route_id))}\n"
        )
        if registration_number:
            admin_text += f"<b>N регистрации:</b> {_copy_link(registration_number)}\n"
        admin_text += (
            f"<b>Водитель:</b> {_copy_link(driver_name)}\n"
            f"<b>ТС:</b> {_copy_link(number_auto or '—')}\n"
        )
        if trailer_number:
            admin_text += f"<b>Прицеп:</b> {_copy_link(trailer_number)}\n"
        if temperature:
            admin_text += f"🌡 Температура: {escape(temperature)}\n"
        admin_text += f"\n<b>Статус точки:</b> {emoji} {status_text}\n"
        if point_type:
            admin_text += f"📦 Тип: {escape(point_type)}\n"
        if point_time:
            admin_text += f"<b>Фактическое время:</b> {format_point_time_display(point_time)}\n"
        if point_date:
            admin_text += f"<b>Плановое время:</b> {escape(point_date)}\n"
        if point_coords:
            admin_text += f"📍 <b>Координаты:</b> {escape(point_coords)}\n"
        if point_odometer:
            admin_text += f"📏 <b>Одометр:</b> {escape(point_odometer)}\n"
        if point_address:
            admin_text += f"📍 Адрес: {escape(point_address)}\n"
        if dispatcher_contacts:
            admin_text += f"\n☎ Контакты: {escape(dispatcher_contacts)}\n"

        for recipient in recipients:
            try:
                await self.bot.send_message(
                    int(recipient.tg_id),
                    admin_text,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Ошибка отправки уведомления пользователю {recipient.tg_id}: {e}")

    async def notify_point_status_reverted(
        self,
        route_id: str,
        point_id: int,
        driver_tg_id: int,
        from_status: str,
        to_status: str,
        point_type: str = "",
        point_place: str = "",
        point_date: str = "",
    ):
        """Уведомить администраторов и логистов об отмене статуса точки водителем."""
        admins = self.user_repository.get_all_active_admins()
        logistics = self.user_repository.get_all_active_logistics()
        recipients = admins + logistics
        if not recipients:
            return
        driver = self.user_repository.get_by_tg_id(int(driver_tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        route_repo = RouteRepository()
        route = route_repo.get_route_info(str(route_id))
        number_auto = (route.number_auto or "—") if route else "—"
        trailer_number = (getattr(route, 'trailer_number', None) or "").strip() if route else ""
        from html import escape
        from urllib.parse import quote
        def _copy_link(text: str) -> str:
            safe = (text or "").strip() or "—"
            return f'<a href="tg://copy?text={quote(safe)}"><code>{escape(safe)}</code></a>'
        status_from_labels = {
            "process": "Выехал на точку",
            "registration": "Зарегистрировался",
            "load": "На воротах",
            "docs": "Забрал документы",
            "success": "Выехал с точки",
        }
        status_to_labels = {
            "new": "новая",
            "process": "Выехал на точку",
            "registration": "Зарегистрировался",
            "load": "На воротах",
            "docs": "Забрал документы",
        }
        from_text = status_from_labels.get(from_status, from_status)
        to_text = status_to_labels.get(to_status, to_status)
        text = (
            "↩️ <b>Водитель отменил статус точки</b>\n\n"
            f"<b>N рейса:</b> {_copy_link(str(route_id))}\n"
            f"<b>Водитель:</b> {_copy_link(driver_name)}\n"
            f"<b>ТС:</b> {_copy_link(number_auto)}\n"
        )
        if trailer_number:
            text += f"<b>Прицеп:</b> {_copy_link(trailer_number)}\n"
        text += f"<b>Был статус:</b> {escape(from_text)}\n"
        text += f"<b>Текущий статус:</b> {escape(to_text)}\n"
        if point_type:
            text += f"📦 Тип точки: {escape(point_type)}\n"
        if point_place:
            text += f"📍 Место: {escape(point_place)}\n"
        if point_date:
            text += f"📅 Дата: {escape(point_date)}\n"
        for r in recipients:
            try:
                await self.bot.send_message(int(r.tg_id), text, parse_mode="HTML")
            except Exception as e:
                print(f"Ошибка отправки уведомления пользователю {r.tg_id}: {e}")

    async def notify_route_cancelled(self, route_id: str, driver_tg_id: int):
        """Уведомить водителя, администраторов и логистов об отмене рейса."""
        driver = self.user_repository.get_by_tg_id(int(driver_tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        route_repo = RouteRepository()
        route = route_repo.get_route_info(str(route_id))
        number_auto = (route.number_auto or "—") if route else "—"

        from html import escape
        from urllib.parse import quote
        def _copy_link(text: str) -> str:
            safe = (text or "").strip() or "—"
            return f'<a href="tg://copy?text={quote(safe)}"><code>{escape(safe)}</code></a>'
        msg = (
            f"🚫 <b>Рейс отменён</b>\n\n"
            f"<b>N рейса:</b> {_copy_link(str(route_id))}\n"
            f"<b>Водитель:</b> {_copy_link(driver_name)}\n"
            f"<b>ТС:</b> {_copy_link(number_auto)}\n"
        )
        recipients = self.user_repository.get_all_active_admins() + self.user_repository.get_all_active_logistics()
        try:
            await self.bot.send_message(int(driver_tg_id), msg, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка уведомления водителя {driver_tg_id}: {e}")
        for r in recipients:
            try:
                await self.bot.send_message(int(r.tg_id), msg, parse_mode="HTML")
            except Exception as e:
                print(f"Ошибка отправки уведомления пользователю {r.tg_id}: {e}")

    async def notify_driver_route_changed(self, route, route_repository: RouteRepository):
        """Уведомить водителя об изменении рейса."""
        if not route or not route.tg_id:
            return
        try:
            text = "✏️ Рейс изменён\n\n"
            text += self._format_route_info_for_driver(route)
            text += "\n\n"
            points_ids = (route.points or "").split(",") if route.points != "0" else []
            if points_ids and points_ids[0] != "0":
                text += "📍 Точки:\n"
                for point_id_str in points_ids:
                    if point_id_str == "0":
                        continue
                    try:
                        point = route_repository.get_point_by_id(int(point_id_str))
                        if point:
                            type_emoji = "📦" if point.type_point == "loading" else "📤"
                            type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
                            text += f"  {type_emoji} {type_text}: {point.place_point} ({point.date_point})\n"
                    except (ValueError, TypeError):
                        continue
            await self.bot.send_message(int(route.tg_id), text, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка уведомления водителю об изменении рейса: {e}")

    async def notify_admins_logistics_route_accepted(self, route_id: str, driver_tg_id: int):
        """Уведомить администраторов и логистов о принятии рейса водителем."""
        driver = self.user_repository.get_by_tg_id(int(driver_tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        admins = self.user_repository.get_all_active_admins()
        logistics = self.user_repository.get_all_active_logistics()
        recipients = admins + logistics
        msg = (
            f"✅ <b>Водитель принял рейс</b>\n\n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"📋 N рейса: {route_id}"
        )
        for r in recipients:
            try:
                await self.bot.send_message(int(r.tg_id), msg, parse_mode="HTML")
            except Exception as e:
                print(f"Ошибка уведомления пользователю {r.tg_id}: {e}")

class MessageSalary:
    """Сервис для отправки уведомлений о зарплате"""
    
    def __init__(self, salary_repository, user_repository):
        self.salary_repository = salary_repository
        self.user_repository = user_repository
        self.bot = Bot(token=settings.TG_TOKEN)

    def _format_salary_for_driver(self, salary: Salary) -> str:
        """
        Форматирует сообщение о зарплате для водителя, показывая все ненулевые параметры.
        Логика синхронизирована с handlers/driver/salary.format_salary_for_driver.
        """
        text = f"📊 Расчет ID: {salary.id}\n"
        text += f"📅 Дата: {salary.date_salary}\n"
        if salary.route_number:
            text += f"🚚 Рейс: {salary.route_number}\n"
        text += "\n"

        field_names = {
            'type_route': 'г/мг/рд/пр',
            'sum_status': 'Окл',
            'sum_daily': 'Сут',
            'load_2_trips': 'Загр 2р',
            'calc_shuttle': 'Шаттл',
            'sum_load_unload': 'Загр/выгр',
            'sum_curtain': 'Штора',
            'sum_return': 'Возврат',
            'sum_add_shuttle': 'Доп шаттл',
            'sum_add_point': 'Доп точка',
            'sum_gas_station': 'АЗС',
            'mileage': 'Пробег',
            'sum_cell_compensation': 'Комп. связи',
            'experience': 'Стаж',
            'percent_10': '10%',
            'sum_bonus': 'Премия',
            'withhold': 'Удержать',
            'compensation': 'Возмещение',
            'dr': 'ДР',
            'sum_without_daily_dr_bonus_exp': 'Без сут/ДР/прем/стажа',
            'sum_without_daily_dr_bonus': 'В день',
            'total': 'ЗП'
        }

        added_fields: List[str] = []
        for field, name in field_names.items():
            value = getattr(salary, field, 0)
            if isinstance(value, (int, float)):
                if value > 0:
                    if field == 'total':
                        added_fields.append(f"💰 {name}: {value:.2f}")
                    else:
                        added_fields.append(f"📝 {name}: {value}")
            elif isinstance(value, str):
                if value and value != "0" and value != " ":
                    added_fields.append(f"📝 {name}: {value}")

        # Поддоны
        pallets_total = salary.pallets_hyper + salary.pallets_metro + salary.pallets_ashan
        if pallets_total > 0:
            added_fields.append(
                f"📦 Паллет: {pallets_total} (гипер: {salary.pallets_hyper}, метро: {salary.pallets_metro}, ашан: {salary.pallets_ashan})"
            )

        # Тарифы за км
        for rate_f, label in [
            ('rate_3km', '3'),
            ('rate_3_5km', '3.5'),
            ('rate_5km', '5'),
            ('rate_10km', '10'),
            ('rate_12km', '12'),
            ('rate_12_5km', '12.5'),
        ]:
            v = getattr(salary, rate_f, 0)
            if v and isinstance(v, (int, float)) and v > 0:
                added_fields.append(f"📝 {label} р/км: {v}")

        # Адреса и транспорт
        if salary.load_address and salary.load_address.strip():
            added_fields.append(f"📍 Загрузка: {salary.load_address}")
        if salary.unload_address and salary.unload_address.strip():
            added_fields.append(f"📍 Выгрузка: {salary.unload_address}")
        if salary.transport and salary.transport.strip():
            added_fields.append(f"🚛 Транспорт: {salary.transport}")
        if salary.trailer_number and salary.trailer_number.strip():
            added_fields.append(f"🛞 Прицеп: {salary.trailer_number}")

        if added_fields:
            text += "\n".join(added_fields)
        else:
            text += "📭 Все значения равны нулю"

        # Статус расчета
        if salary.status_driver == "confirmed":
            text += "\n\n✅ Статус: Подтверждено"
        elif salary.status_driver == "commented":
            text += f"\n\n💬 Статус: С комментарием\n📋 Комментарий: {salary.comment_driver}"
        else:
            text += "\n\n⏳ Статус: Ожидает подтверждения"

        return text

    def get_salary_confirmation_keyboard(self, salary_id: int):
        """Создает клавиатуру с кнопками подтверждения и комментария"""
        builder = InlineKeyboardBuilder()
        builder.add(
            types.InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_salary_{salary_id}"),
            types.InlineKeyboardButton(text="💬 Комментарий", callback_data=f"comment_salary_{salary_id}")
        )
        return builder.as_markup()

    async def notify_driver_about_salary(self, id_driver, date_salary):
        """Уведомить водителя о ЗП за день"""
        # Получаем последний расчет за указанную дату
        salary = self.salary_repository.get_last_by_driver_date(id_driver, date_salary)
        
        if not salary:
            print(f"Расчет для водителя {id_driver} за {date_salary} не найден")
            return
        
        text = self._format_salary_for_driver(salary)
        keyboard = self.get_salary_confirmation_keyboard(salary.id)
        
        try:
            await self.bot.send_message(
                int(id_driver), 
                f"💰 Поступил расчет\n\n{text}",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Ошибка отправки уведомления о зарплате водителю {id_driver}: {e}")
    
    async def notify_accountants_about_salary_confirmation(self, driver_name: str, salary_id: int, date_salary: str, zp: float):
        """Уведомить бухгалтеров и администраторов о подтверждении расчета водителем"""
        accountants = self.user_repository.get_all_active_accountants()
        admins = self.user_repository.get_all_active_admins()
        recipients = accountants + admins
        
        # Пытаемся получить полный расчет для вывода всех ненулевых полей
        salary_details = ""
        try:
            salary = self.salary_repository.get_by_id_int(salary_id)
            if salary:
                salary_details = "\n\n" + self._format_salary_for_driver(salary)
        except Exception as e:
            print(f"Ошибка при получении расчета {salary_id} для уведомления: {e}")
        
        for recipient in recipients:
            try:
                await self.bot.send_message(
                    int(recipient.tg_id),
                    f"✅ Водитель {copy_link_fio(driver_name)} подтвердил расчет:\n\n"
                    f"📊 ID расчета: {salary_id}\n"
                    f"📅 Дата: {html.escape(date_salary)}\n"
                    f"💰 ЗП: {zp:.2f}"
                    f"{salary_details}",
                    parse_mode="HTML",
                )
            except Exception as e:
                print(f"Не удалось отправить уведомление бухгалтеру/админу {recipient.tg_id}: {e}")
    
    async def notify_accountants_about_salary_comment(self, driver_name: str, salary_id: int, date_salary: str, comment: str):
        """Уведомить бухгалтеров и администраторов о комментарии к расчету"""
        accountants = self.user_repository.get_all_active_accountants()
        admins = self.user_repository.get_all_active_admins()
        recipients = accountants + admins
        
        salary_details = ""
        try:
            salary = self.salary_repository.get_by_id_int(salary_id)
            if salary:
                salary_details = "\n\n" + self._format_salary_for_driver(salary)
        except Exception as e:
            print(f"Ошибка при получении расчета {salary_id} для уведомления о комментарии: {e}")
        
        for recipient in recipients:
            try:
                await self.bot.send_message(
                    int(recipient.tg_id),
                    f"💬 Водитель {copy_link_fio(driver_name)} оставил комментарий к расчету:\n\n"
                    f"📊 ID расчета: {salary_id}\n"
                    f"📅 Дата: {html.escape(date_salary)}\n"
                    f"💬 Комментарий: {html.escape(comment)}"
                    f"{salary_details}",
                    parse_mode="HTML",
                )
            except Exception as e:
                print(f"Не удалось отправить уведомление бухгалтеру/админу {recipient.tg_id}: {e}")