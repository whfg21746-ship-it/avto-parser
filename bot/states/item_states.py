from aiogram.fsm.state import State, StatesGroup


class AddItemFSM(StatesGroup):
    choosing_method = State()
    # Method A: paste URL
    waiting_url = State()
    # Method B: build URL
    entering_search_query = State()
    choosing_city = State()
    entering_city = State()
    entering_search_price_max = State()
    confirming_built_url = State()
    # Common steps (both methods)
    entering_name = State()
    choosing_category = State()
    entering_new_category = State()
    choosing_custom_prompt = State()
    entering_custom_prompt = State()
    confirming = State()


class EditItemFSM(StatesGroup):
    entering_url = State()
    entering_custom_prompt = State()


class AddCategoryFSM(StatesGroup):
    entering_name = State()
    choosing_custom_prompt = State()
    entering_custom_prompt = State()


class EditCategoryPromptFSM(StatesGroup):
    entering_custom_prompt = State()


class RenameCategoryFSM(StatesGroup):
    entering_name = State()


class SettingsFSM(StatesGroup):
    entering_interval = State()
    entering_proxy = State()
    entering_max_seller = State()
    entering_city = State()
    entering_min_profit = State()
