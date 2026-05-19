"""
Telegram-бот для проекта «Цифровая исповедь».
Собирает анкеты участников и пересылает их в командный чат.

Все настройки — через переменные окружения (см. README.md).
"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)


# === КОНФИГ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
TEAM_CHAT_ID = os.getenv("TEAM_CHAT_ID")  # ID командного чата (например, -1001234567890)

if not BOT_TOKEN:
    raise RuntimeError("8967974561:AAFNuz8BJfdAvUuB5y2LhaTqDURUFyGa22E")
if not TEAM_CHAT_ID:
    raise RuntimeError(-1003503064558)

TEAM_CHAT_ID = int(TEAM_CHAT_ID)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("digital_confession_bot")


# === СОСТОЯНИЯ ДИАЛОГА ===
class Form(StatesGroup):
    name = State()
    age = State()
    city = State()
    phone = State()
    video = State()


# === КЛАВИАТУРЫ ===
def start_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📝 Поделиться историей")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить мой номер", request_contact=True)],
            [KeyboardButton(text="Пропустить")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def video_skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Записать позже")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# === ТЕКСТЫ ===
WELCOME = (
    "👋 Здравствуйте.\n\n"
    "Мы собираем личные истории людей со всей России. Каждая история становиться монологом цифрового аватара - лица и имени участника никто не узнает.\n\n" 
"Из этих историй мы соберем документальный фильм, одна из целей которого дать понять, что мы не одиноки в своих переживаниях.\n\n"
"Заполните короткую анкету и расскажите нам, что вас волнует.\n\n"
)

ASK_NAME = (
    "Как к вам обращаться?\n\n"
    "<i>Можно настоящее имя или псевдоним — как удобно.</i>"
)

ASK_AGE = "Сколько вам лет?"

ASK_CITY = (
    "Из какого вы города или региона?\n\n"
    "<i>Это поможет команде понять, насколько широка география проекта.</i>"
)

ASK_PHONE = (
    "Как с вами связаться?\n\n"
    "Можно <b>поделиться номером</b> (через кнопку ниже) или <b>прислать текстом</b>:\n"
    "— номер телефона\n"
    "— email\n"
    "— или ваш ник в Telegram (например, @username)\n\n"
    "Если не готовы — нажмите «Пропустить», команда напишет вам прямо в чате."
)

ASK_VIDEO = (
    "Расскажите свою историю — в любой форме, как удобно:\n\n"
    "📹 <b>Видео-кружок</b> — нажмите на иконку микрофона и переключите её в режим круга\n"
    "🎬 <b>Видео-файл</b> — снимите на телефон и пришлите в чат\n"
    "🔗 <b>Ссылка</b> — на Яндекс.Диск, Google Drive, YouTube или другое облако\n\n"
    "Рекомендации по съёмке: горизонтальная ориентация, лицо в кадре, чистый звук, "
    "длительность 3–10 минут. Подробнее — на сайте проекта.\n\n"
    "Если хотите подумать и записать позже — нажмите кнопку ниже, мы свяжемся с вами."
)

THANK_YOU = (
    "🙏 Спасибо. Заявка получена.\n\n"
    "<b>Что дальше:</b>\n"
    "— Команда внимательно посмотрит ваш материал\n"
    "— Свяжемся с вами в течение 3 рабочих дней по контактам, которые вы оставили\n"
    "— Расскажем, как происходит создание аватара и обсудим детали\n\n"
    "Если возникнут вопросы — напишите команде напрямую:\n"
    "• Иван Левшин — vk.com/vsezaboogaloo\n"
    "• Сергей Гавриков — vk.com/sergegavrikov\n"
    "• или общий email: hello@1147.ru\n\n"
    "До связи."
)

CANCELLED = (
    "Хорошо, мы остановились. Когда захотите вернуться — просто напишите /start, "
    "и начнём заново.\n\n"
    "Спасибо, что прислушались к проекту."
)


# === ОБРАБОТЧИКИ ===
dp = Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME, reply_markup=start_kb())


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(CANCELLED, reply_markup=ReplyKeyboardRemove())


@dp.message(F.text == "📝 Поделиться историей")
async def begin_form(message: Message, state: FSMContext) -> None:
    await state.set_state(Form.name)
    await message.answer(ASK_NAME, reply_markup=ReplyKeyboardRemove())


# ИМЯ
@dp.message(Form.name, F.text)
async def step_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2 or len(name) > 60:
        await message.answer("Похоже на ошибку — напишите имя ещё раз (2–60 символов).")
        return
    await state.update_data(name=name)
    await state.set_state(Form.age)
    await message.answer(ASK_AGE)


# ВОЗРАСТ
@dp.message(Form.age, F.text)
async def step_age(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    # Достаём число из текста
    m = re.search(r"\d+", raw)
    if not m:
        await message.answer("Пожалуйста, напишите возраст числом — например, 34.")
        return
    age = int(m.group())
    if age < 14 or age > 100:
        await message.answer(
            "Возраст должен быть от 14 до 100. Если вам меньше 18 — мы расскажем об "
            "особенностях участия и возьмём согласие от родителя или опекуна."
        )
        return
    await state.update_data(age=age)
    await state.set_state(Form.city)
    await message.answer(ASK_CITY)


# ГОРОД
@dp.message(Form.city, F.text)
async def step_city(message: Message, state: FSMContext) -> None:
    city = message.text.strip()
    if len(city) < 2 or len(city) > 80:
        await message.answer("Напишите город ещё раз — например, «Нижний Новгород» или «Сибирь».")
        return
    await state.update_data(city=city)
    await state.set_state(Form.phone)
    await message.answer(ASK_PHONE, reply_markup=phone_kb())


# ТЕЛЕФОН / КОНТАКТ
@dp.message(Form.phone, F.contact)
async def step_phone_contact(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number
    await state.update_data(contact=f"📱 {phone}")
    await state.set_state(Form.video)
    await message.answer(ASK_VIDEO, reply_markup=video_skip_kb())


@dp.message(Form.phone, F.text == "Пропустить")
async def step_phone_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(contact="— не указано (пользователь пропустил) —")
    await state.set_state(Form.video)
    await message.answer(ASK_VIDEO, reply_markup=video_skip_kb())


@dp.message(Form.phone, F.text)
async def step_phone_text(message: Message, state: FSMContext) -> None:
    contact = message.text.strip()
    if len(contact) < 3 or len(contact) > 120:
        await message.answer("Похоже на ошибку. Пришлите номер, email или Telegram-ник ещё раз.")
        return
    await state.update_data(contact=contact)
    await state.set_state(Form.video)
    await message.answer(ASK_VIDEO, reply_markup=video_skip_kb())


# ВИДЕО — три варианта приёма
@dp.message(Form.video, F.video_note)
async def step_video_note(message: Message, state: FSMContext) -> None:
    await state.update_data(video_kind="video_note", video_file_id=message.video_note.file_id)
    await finish_form(message, state)


@dp.message(Form.video, F.video)
async def step_video_file(message: Message, state: FSMContext) -> None:
    await state.update_data(video_kind="video", video_file_id=message.video.file_id)
    await finish_form(message, state)


@dp.message(Form.video, F.document)
async def step_video_document(message: Message, state: FSMContext) -> None:
    # Файл может быть приложен как документ (особенно с iPhone)
    await state.update_data(video_kind="document", video_file_id=message.document.file_id)
    await finish_form(message, state)


@dp.message(Form.video, F.text == "Записать позже")
async def step_video_later(message: Message, state: FSMContext) -> None:
    await state.update_data(video_kind="later", video_link=None)
    await finish_form(message, state)


@dp.message(Form.video, F.text)
async def step_video_link(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text.startswith(("http://", "https://")):
        await state.update_data(video_kind="link", video_link=text)
        await finish_form(message, state)
    else:
        await message.answer(
            "Это не похоже на видео или ссылку. Пришлите видео-кружок, видео-файл "
            "или ссылку (начинается с https://...). Или нажмите «Записать позже»."
        )


# === ФИНАЛ ===
async def finish_form(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    user = message.from_user

    # Безопасно отображаем юзернейм
    username_line = f"@{user.username}" if user.username else f"id {user.id}"

    summary = (
        f"<b>🎬 НОВАЯ ЗАЯВКА</b>\n"
        f"<i>Цифровая исповедь · бот</i>\n\n"
        f"<b>Имя:</b> {html.quote(data.get('name', '—'))}\n"
        f"<b>Возраст:</b> {data.get('age', '—')}\n"
        f"<b>Город:</b> {html.quote(data.get('city', '—'))}\n"
        f"<b>Контакт:</b> {html.quote(data.get('contact', '—'))}\n"
        f"<b>Telegram:</b> {username_line}\n"
    )

    kind = data.get("video_kind")
    if kind == "link":
        summary += f"\n<b>Видео:</b> ссылка → {html.quote(data['video_link'])}"
    elif kind == "later":
        summary += "\n<b>Видео:</b> участник запишет позже — нужна связь."
    else:
        summary += "\n<b>Видео:</b> прикреплено ниже ⬇️"

    # Отправляем сводку в командный чат
    try:
        await bot_global.send_chat_action(TEAM_CHAT_ID, ChatAction.TYPING)
        await bot_global.send_message(TEAM_CHAT_ID, summary)

        # Если есть медиа — отправляем отдельным сообщением, чтобы видно было сразу
        if kind == "video_note":
            await bot_global.send_video_note(TEAM_CHAT_ID, data["video_file_id"])
        elif kind == "video":
            await bot_global.send_video(TEAM_CHAT_ID, data["video_file_id"])
        elif kind == "document":
            await bot_global.send_document(TEAM_CHAT_ID, data["video_file_id"])

        log.info("Forwarded application from %s to team chat", username_line)
    except Exception as e:
        log.exception("Failed to forward application: %s", e)
        # Если не получилось переслать — хотя бы покажем участнику успех,
        # ошибки в команде разберём по логам
        pass

    await state.clear()
    await message.answer(THANK_YOU, reply_markup=ReplyKeyboardRemove())


# === FALLBACK ===
@dp.message()
async def fallback(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer(
            "Чтобы начать заявку — нажмите /start. Чтобы остановить диалог — /cancel."
        )
    else:
        await message.answer(
            "Не понял ответ. Если запутались — напишите /cancel и начнём заново через /start."
        )


# === ЗАПУСК ===
bot_global: Bot | None = None


async def main() -> None:
    global bot_global
    bot_global = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    log.info("Бот запускается...")
    try:
        # Проверяем, что у бота есть доступ к командному чату
        chat = await bot_global.get_chat(TEAM_CHAT_ID)
        log.info("Командный чат подключён: %s", chat.title or chat.id)
    except Exception as e:
        log.error("Не удалось подключиться к командному чату %s: %s", TEAM_CHAT_ID, e)
        log.error("Убедитесь, что бот добавлен в чат и сделан администратором.")

    await dp.start_polling(bot_global)


if __name__ == "__main__":
    asyncio.run(main())
