from aiogram.fsm.state import State, StatesGroup

class SalaryState(StatesGroup):
    driver = State()
    salary = State()

class DriverSalaryDateState(StatesGroup):
    date = State()

class AdminSalaryDateState(StatesGroup):
    driver = State()
    date = State()

class DeleteSalaryState(StatesGroup):
    driver = State()
    date = State()
    salary_id = State()  # Добавляем новое состояние для выбора ID
    confirmation = State()

class DriverCommentState(StatesGroup):
    comment = State()

# РАЗДЕЛИЛИ состояния для водителя и администратора
class DriverExportPeriodState(StatesGroup):
    period_type = State()
    custom_start = State()
    custom_end = State()
    month_year = State()

class AdminExportPeriodState(StatesGroup):
    driver = State()
    period_type = State()
    custom_start = State()
    custom_end = State()
    month_year = State()