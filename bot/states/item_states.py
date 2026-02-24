from aiogram.fsm.state import State, StatesGroup


class AddItemFSM(StatesGroup):
    choosing_search_query = State()
    entering_name = State()
    entering_model_pattern = State()
    entering_storage = State()
    entering_threshold = State()
    entering_market_price = State()
    confirming = State()


class EditItemFSM(StatesGroup):
    entering_threshold = State()
    entering_market_price = State()


class AddCategoryFSM(StatesGroup):
    entering_name = State()
    entering_avito_id = State()


class AddSearchQueryFSM(StatesGroup):
    choosing_category = State()
    entering_keyword = State()  # Accepts keyword or full Avito URL
    entering_price_max = State()
    confirming = State()


class SettingsFSM(StatesGroup):
    entering_interval = State()
    entering_proxy = State()
    entering_max_seller = State()


class DiscoveryFSM(StatesGroup):
    running = State()
