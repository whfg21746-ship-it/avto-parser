from aiogram.fsm.state import State, StatesGroup


class AddItemFSM(StatesGroup):
    choosing_category = State()
    entering_name = State()
    entering_avito_params = State()
    entering_threshold = State()
    entering_market_price = State()
    confirming = State()


class EditItemFSM(StatesGroup):
    entering_threshold = State()
    entering_market_price = State()


class AddCategoryFSM(StatesGroup):
    entering_name = State()
    entering_avito_id = State()


class SettingsFSM(StatesGroup):
    entering_interval = State()
    entering_proxy = State()
    entering_max_seller = State()
