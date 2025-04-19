from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiogram.contrib.middlewares.logging import LoggingMiddleware
import logging
import random
import json

API_TOKEN = '7820313475:AAFEr3gRknL9BtCnZ1QsTi84CsT2hmQOO40'  # 🔐 Вставь сюда свой токен

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

START_BALANCE = 1000

players = {}  # user_id: dict
used_promos = set()
available_promos = {
    "bonus100": 100,
    "free20000": 20000
}

# 📋 Главное меню с WebApp
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(
    KeyboardButton("🎮 Играть"),
    KeyboardButton("📋 Команды"),
    KeyboardButton("💰 Баланс"),
    KeyboardButton("🏆 Топ"),
    KeyboardButton(text="🎡 Колесо фортуны", web_app=WebAppInfo(url="https://mines-game-web.vercel.app/"))  # ЗАМЕНИ
)


@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.full_name
    if user_id not in players:
        players[user_id] = {
            'username': username,
            'balance': START_BALANCE,
            'active_game': False,
            'games_played': 0
        }
    await message.answer(
        f"👋 Привет, {username}!\n💰 Баланс: {players[user_id]['balance']} mCoin",
        reply_markup=main_menu
    )
    await cmd_help(message)


@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    text = (
        "🛠 <b>Доступные команды:</b>\n\n"
        "🎮 <b>/mines</b> <code>ставка</code> <code>мины</code> — начать игру\n"
        "💰 <b>/balance</b> — проверить свой баланс\n"
        "🎁 <b>/promo</b> <code>код</code> — активировать промокод\n"
        "🏆 <b>/top</b> — топ игроков по балансу\n"
        "📋 <b>/help</b> — это меню с подсказками\n\n"
        "🔹 Пример: <code>/mines 100 3</code>"
    )
    await message.answer(text, parse_mode='HTML')


@dp.message_handler(commands=['balance'])
async def cmd_balance(message: types.Message):
    user_id = message.from_user.id
    player = players.get(user_id)
    if not player:
        await message.reply("Сначала напиши /start.")
        return
    await message.reply(f"💰 Баланс: {player['balance']} mCoin")


@dp.message_handler(commands=['top'])
async def top_players(message: types.Message):
    if not players:
        await message.reply("Ещё нет игроков.")
        return

    sorted_players = sorted(players.items(), key=lambda x: x[1]['balance'], reverse=True)
    top_list = "\n".join(
        [f"{i+1}. {p[1]['username']} — {p[1]['balance']} mCoin | 🎮 Игр: {p[1].get('games_played', 0)}"
         for i, p in enumerate(sorted_players[:10])]
    )
    await message.reply(f"🏆 <b>Топ игроков:</b>\n\n{top_list}", parse_mode='HTML')


@dp.message_handler(commands=['promo'])
async def promo_code(message: types.Message):
    user_id = message.from_user.id
    args = message.get_args().strip().lower()
    if not args:
        await message.reply("❗ Формат: /promo <код>")
        return
    if args not in available_promos:
        await message.reply("⛔ Неверный или просроченный промокод.")
        return
    if (user_id, args) in used_promos:
        await message.reply("⚠️ Этот промокод уже активирован.")
        return

    reward = available_promos[args]
    players[user_id]['balance'] += reward
    used_promos.add((user_id, args))
    await message.reply(f"✅ Промокод активирован!\n💰 Вы получили {reward} mCoin")


@dp.message_handler(commands=['mines'])
async def cmd_mines(message: types.Message):
    user_id = message.from_user.id
    player = players.get(user_id)
    if not player:
        await message.reply("Сначала напиши /start.")
        return

    args = message.get_args().split()
    if len(args) != 2 or not args[0].isdigit() or not args[1].isdigit():
        await message.reply("❗ Формат: /mines <ставка> <мины>\nПример: /mines 100 3")
        return

    bet = int(args[0])
    mine_count = int(args[1])

    if bet < 1 or mine_count < 1 or mine_count >= 25:
        await message.reply("⚠️ Минимальная ставка — 1\nМин должно быть от 1 до 24")
        return

    if player['balance'] < bet:
        await message.reply("Недостаточно mCoin для ставки.")
        return

    # Старт игры
    player.update({
        'active_game': True,
        'bet': bet,
        'mines': set(random.sample(range(25), mine_count)),
        'clicked': set(),
        'win_multiplier': 1.0,
        'win_amount': bet,
        'balance': player['balance'] - bet,
        'games_played': player.get('games_played', 0) + 1
    })

    await message.reply(
        f"🎮 Игра началась!\n💣 Мин: {mine_count}\n💸 Ставка: {bet} mCoin\n"
        f"💰 Выигрыш: x1 / {bet} mCoin",
        reply_markup=make_game_keyboard(set())
    )


def make_game_keyboard(clicked):
    keyboard = InlineKeyboardMarkup(row_width=5)
    buttons = []
    for i in range(25):
        if i in clicked:
            buttons.append(InlineKeyboardButton("✅", callback_data="skip"))
        else:
            buttons.append(InlineKeyboardButton("🎁", callback_data=f"cell_{i}"))
    keyboard.add(*buttons)
    keyboard.add(InlineKeyboardButton("💸 Забрать выигрыш", callback_data="cashout"))
    return keyboard


@dp.callback_query_handler(lambda c: c.data.startswith('cell_'))
async def process_cell(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    player = players.get(user_id)
    if not player or not player.get('active_game'):
        await callback_query.answer("Нет активной игры.")
        return

    cell = int(callback_query.data.split("_")[1])
    if cell in player['clicked']:
        await callback_query.answer("Уже открыта.")
        return

    if cell in player['mines']:
        player['active_game'] = False
        await bot.edit_message_text(
            f"💥 БУМ! Ты попал на мину!\n❌ Вы проиграли ставку {player['bet']} mCoin.\n"
            f"💰 Баланс: {player['balance']} mCoin",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id
        )
        return

    player['clicked'].add(cell)
    player['win_multiplier'] += 0.03
    player['win_amount'] = int(player['bet'] * player['win_multiplier'])

    await bot.edit_message_text(
        f"💣 Мин: {len(player['mines'])}\n💸 Ставка: {player['bet']} mCoin\n"
        f"💰 Выигрыш: x{round(player['win_multiplier'], 2)} / {player['win_amount']} mCoin",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=make_game_keyboard(player['clicked'])
    )


@dp.callback_query_handler(lambda c: c.data == 'cashout')
async def cashout(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    player = players.get(user_id)
    if not player or not player.get('active_game'):
        await callback_query.answer("Нет активной игры.")
        return

    player['balance'] += player['win_amount']
    player['active_game'] = False

    await bot.edit_message_text(
        f"🎉 Вы забрали выигрыш!\n💰 Вы получили {player['win_amount']} mCoin\n"
        f"📦 Баланс: {player['balance']} mCoin",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id
    )


@dp.callback_query_handler(lambda c: c.data == 'skip')
async def skip_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("Клетка уже открыта.")


# 📩 Получение данных из WebApp
@dp.message_handler(content_types=types.ContentType.WEB_APP_DATA)
async def handle_web_app_data(message: types.Message):
    data = message.web_app_data.data  # строка
    user_id = message.from_user.id

    try:
        parsed = json.loads(data)
        win_amount = parsed.get("win", 0)

        if user_id in players:
            players[user_id]['balance'] += win_amount
            await message.answer(f"🎉 Вы выиграли {win_amount} mCoin в колесе фортуны!\n💰 Новый баланс: {players[user_id]['balance']} mCoin")
        else:
            await message.answer("⚠️ Ошибка: игрок не найден.")
    except Exception as e:
        await message.answer("❌ Ошибка при обработке данных из WebApp.")


# Кнопки
@dp.message_handler(lambda message: message.text == "📋 Команды")
async def show_help_menu(message: types.Message):
    await cmd_help(message)


@dp.message_handler(lambda message: message.text == "💰 Баланс")
async def button_balance(message: types.Message):
    await cmd_balance(message)


@dp.message_handler(lambda message: message.text == "🏆 Топ")
async def button_top(message: types.Message):
    await top_players(message)


@dp.message_handler(lambda message: message.text == "🎮 Играть")
async def game_instruction(message: types.Message):
    await message.answer(
        "🎮 Чтобы начать игру, введи команду:\n\n"
        "<code>/mines [ставка] [мины]</code>\n\n"
        "📌 Пример: <code>/mines 100 3</code>",
        parse_mode='HTML'
    )


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
