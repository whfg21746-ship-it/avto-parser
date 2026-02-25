import json
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.menus import back_main_keyboard, settings_keyboard
from bot.states.item_states import SettingsFSM
from db.models import get_setting, set_setting

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery) -> None:
    monitoring = await get_setting("monitoring_enabled")
    interval = await get_setting("scan_interval_seconds") or "60"
    max_seller = await get_setting("max_seller_items") or "10"
    city = await get_setting("city")
    proxy_raw = await get_setting("proxy_list")

    try:
        proxies = json.loads(proxy_raw) if proxy_raw else []
    except json.JSONDecodeError:
        proxies = []

    send_check = await get_setting("send_check_verdicts")
    min_profit = await get_setting("min_profit_percent") or "0"

    mon_status = "\u25b6\ufe0f Включён" if monitoring == "true" else "\u23f8 Выключен"
    city_display = city if city else "Вся Россия"
    check_status = "\u274c Выкл" if send_check == "false" else "\u2705 Вкл"
    profit_display = f"{min_profit}%" if min_profit != "0" else "не задан"

    text = (
        "\u2699\ufe0f Настройки:\n\n"
        f"\U0001f30d Город: {city_display}\n"
        f"\U0001f4e1 Мониторинг: {mon_status}\n"
        f"\u23f1 Интервал: {interval} сек\n"
        f"\U0001f464 Макс. объявлений продавца: {max_seller}\n"
        f"\U0001f4e1 Прокси: {len(proxies)} шт.\n"
        f"\U0001f50d CHECK алерты: {check_status}\n"
        f"\U0001f4b0 Мин. профит: {profit_display}"
    )
    await callback.message.edit_text(text, reply_markup=settings_keyboard())
    await callback.answer()


# --- City ---

@router.callback_query(F.data == "setting_city")
async def start_edit_city(callback: CallbackQuery, state: FSMContext) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001f30d Вся Россия", callback_data="set_city_all")],
        [InlineKeyboardButton(text="\u270f\ufe0f Ввести город", callback_data="set_city_enter")],
        [InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="settings")],
    ])
    await callback.message.edit_text(
        "Выберите город/регион:",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data == "set_city_all")
async def set_city_all(callback: CallbackQuery) -> None:
    await set_setting("city", "")
    await set_setting("city_slug", "rossiya")
    await callback.answer("\u2705 Город: Вся Россия")

    # Return to settings
    await show_settings(callback)


@router.callback_query(F.data == "set_city_enter")
async def set_city_enter(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.entering_city)
    await callback.message.edit_text(
        "Введите название города по-русски (например: Ставрополь, Москва, Краснодар).\n\n"
        "Бот автоматически сконвертирует в формат Авито.",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


# Cyrillic to Latin transliteration for Avito URL slugs
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

# Common cities with known Avito slugs
_CITY_SLUGS = {
    "москва": "moskva",
    "санкт-петербург": "sankt-peterburg",
    "петербург": "sankt-peterburg",
    "спб": "sankt-peterburg",
    "новосибирск": "novosibirsk",
    "екатеринбург": "ekaterinburg",
    "казань": "kazan",
    "нижний новгород": "nizhniy_novgorod",
    "краснодар": "krasnodar",
    "ставрополь": "stavropol",
    "ростов-на-дону": "rostov-na-donu",
    "ростов": "rostov-na-donu",
    "самара": "samara",
    "уфа": "ufa",
    "красноярск": "krasnoyarsk",
    "воронеж": "voronezh",
    "пермь": "perm",
    "волгоград": "volgograd",
    "челябинск": "chelyabinsk",
    "омск": "omsk",
    "сочи": "sochi",
    "тюмень": "tyumen",
    "владивосток": "vladivostok",
    "хабаровск": "habarovsk",
    "иркутск": "irkutsk",
    "барнаул": "barnaul",
    "тула": "tula",
    "рязань": "ryazan",
    "калининград": "kaliningrad",
    "саратов": "saratov",
    "томск": "tomsk",
    "курск": "kursk",
    "тверь": "tver",
    "белгород": "belgorod",
    "ярославль": "yaroslavl",
}


def _city_to_slug(city_name: str) -> str:
    city_lower = city_name.lower().strip()

    # Check known cities first
    if city_lower in _CITY_SLUGS:
        return _CITY_SLUGS[city_lower]

    # Transliterate
    result = []
    for ch in city_lower:
        if ch in _TRANSLIT:
            result.append(_TRANSLIT[ch])
        elif ch == " ":
            result.append("-")
        elif ch == "-":
            result.append("-")
        elif ch.isascii() and ch.isalnum():
            result.append(ch)
    return "".join(result) or "rossiya"


@router.message(SettingsFSM.entering_city)
async def process_city(message: Message, state: FSMContext) -> None:
    city_name = message.text.strip()
    if not city_name:
        await message.answer("Город не может быть пустым:")
        return

    slug = _city_to_slug(city_name)
    await set_setting("city", city_name)
    await set_setting("city_slug", slug)
    await state.clear()
    await message.answer(
        f"\u2705 Город установлен: {city_name} ({slug})",
        reply_markup=back_main_keyboard(),
    )


# --- Interval ---

@router.callback_query(F.data == "setting_interval")
async def start_edit_interval(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.entering_interval)
    await callback.message.edit_text(
        "Введи новый интервал сканирования (в секундах):",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(SettingsFSM.entering_interval)
async def process_interval(message: Message, state: FSMContext) -> None:
    try:
        interval = int(message.text.strip())
        if interval < 10:
            await message.answer("Минимальный интервал — 10 секунд:")
            return
    except (ValueError, AttributeError):
        await message.answer("Введи число:")
        return

    await set_setting("scan_interval_seconds", str(interval))
    await state.clear()
    await message.answer(
        f"\u2705 Интервал установлен: {interval} сек",
        reply_markup=back_main_keyboard(),
    )


# --- Proxy ---

@router.callback_query(F.data == "setting_proxy")
async def start_edit_proxy(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.entering_proxy)
    await callback.message.edit_text(
        "Введи список прокси (JSON массив):\n"
        'Пример: ["http://user:pass@host:port"]\n\n'
        'Отправь "clear" чтобы очистить.',
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(SettingsFSM.entering_proxy)
async def process_proxy(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text.lower() == "clear":
        await set_setting("proxy_list", "[]")
        await state.clear()
        await message.answer(
            "\u2705 Прокси очищены.",
            reply_markup=back_main_keyboard(),
        )
        return

    try:
        proxies = json.loads(text)
        if not isinstance(proxies, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        await message.answer("Некорректный JSON. Отправь массив строк:")
        return

    await set_setting("proxy_list", json.dumps(proxies))
    await state.clear()
    await message.answer(
        f"\u2705 Прокси обновлены: {len(proxies)} шт.",
        reply_markup=back_main_keyboard(),
    )


# --- Max Seller Items ---

@router.callback_query(F.data == "setting_max_seller")
async def start_edit_max_seller(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.entering_max_seller)
    await callback.message.edit_text(
        "Введи максимальное кол-во объявлений продавца\n"
        "(продавцы с большим кол-вом будут отфильтрованы):",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(SettingsFSM.entering_max_seller)
async def process_max_seller(message: Message, state: FSMContext) -> None:
    try:
        val = int(message.text.strip())
        if val < 1:
            await message.answer("Введи число больше 0:")
            return
    except (ValueError, AttributeError):
        await message.answer("Введи число:")
        return

    await set_setting("max_seller_items", str(val))
    await state.clear()
    await message.answer(
        f"\u2705 Макс. объявлений продавца: {val}",
        reply_markup=back_main_keyboard(),
    )


# --- CHECK Verdicts Toggle ---

@router.callback_query(F.data == "setting_check_verdicts")
async def toggle_check_verdicts(callback: CallbackQuery) -> None:
    current = await get_setting("send_check_verdicts")
    new_value = "false" if current != "false" else "true"
    await set_setting("send_check_verdicts", new_value)

    status = "\u2705 Включены" if new_value == "true" else "\u274c Выключены"
    await callback.answer(f"CHECK алерты: {status}")
    await show_settings(callback)


# --- Min Profit Percent ---

@router.callback_query(F.data == "setting_min_profit")
async def start_edit_min_profit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.entering_min_profit)
    current = await get_setting("min_profit_percent") or "0"
    await callback.message.edit_text(
        f"Текущий минимальный профит: {current}%\n\n"
        "Введи минимальный процент профита для алерта (0 = без фильтра):",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(SettingsFSM.entering_min_profit)
async def process_min_profit(message: Message, state: FSMContext) -> None:
    try:
        val = int(message.text.strip())
        if val < 0:
            await message.answer("Процент не может быть отрицательным:")
            return
    except (ValueError, AttributeError):
        await message.answer("Введи число:")
        return

    await set_setting("min_profit_percent", str(val))
    await state.clear()
    display = f"{val}%" if val > 0 else "не задан (все алерты)"
    await message.answer(
        f"\u2705 Мин. профит для алерта: {display}",
        reply_markup=back_main_keyboard(),
    )
