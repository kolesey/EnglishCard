import os, sys
from config import OTHER_WORDS_COUNT, ACTIVATE_THIS_PATH
if sys.platform != 'win32':
    with open(ACTIVATE_THIS_PATH) as f:
         exec(f.read(), {'__file__': ACTIVATE_THIS_PATH})

from dotenv import load_dotenv
load_dotenv()

import random

from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup

from db.db import create_db_connection, add_user, find_user, add_words, take_random_word, count_words, take_other_words, \
    del_word, add_rigt_answer, add_wrong_answer
from random_word.random_word import get_random_word
from yandex_translate.yandex_translate import translate

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

if TELEGRAM_TOKEN is None:
    raise ValueError('TELEGRAM_TOKEN не установлен в переменных окружения.')

print('Start telegram bot...')

state_storage = StateMemoryStorage()
bot = TeleBot(TELEGRAM_TOKEN, state_storage=state_storage)

buttons = []


def show_hint(*lines):
    return '\n'.join(lines)


def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"


class Command:
    ADD_WORD = 'Добавить слово ➕'
    ADD_RAND_WORD = 'Добавить случайное слово'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'
    CANCEL = '=Отмена='

class MyStates(StatesGroup):
    waitng_for_name = State()
    waitng_for_word = State()
    check_answer = State()
    save_word = State()
    delete_word = State()


def main_dialog(message):
    """
    Функция проверяет наличие минимального количества слов в словаре/
    В зависимости от количества слов, либо предлагает ввести новое слово в словарь, либо выводит основной диалог
    :param message:
    :return:
    """

    cid = message.chat.id
    conn = create_db_connection()
    # Получаем количество слов пользователя в словаре
    dict_len = count_words(conn, cid)
    conn.close()

    # Проверяем наличие минимального количества слов в словаре
    if dict_len < OTHER_WORDS_COUNT:
        # Устанавливаем стэйт на ожидание ввода слова для словаря
        bot.set_state(message.from_user.id, MyStates.waitng_for_word, cid)
        bot.send_message(cid, "У Вас в словаре мало слов. "
                              "Введите слово, которое хотите добавить.",
                         reply_markup=types.ReplyKeyboardRemove())
    else:
        # Выводим основной диалог игры
        create_cards(message)


def create_cards(message):
    """
    Функция построения основного диалога игры
    :param message:
    :return:
    """
    cid = message.chat.id
    markup = types.ReplyKeyboardMarkup(row_width=2)

    global buttons
    buttons = []
    conn = create_db_connection()
    # Получаем из БД пару слов
    pair = list(take_random_word(conn, cid))
    rus_word = pair[0]

    # Перемешиваем направление перевода en-ru или ru-en
    random.shuffle(pair)
    translate = pair[0]
    target_word = pair[1]

    # Запрашиваем остальные слова в зависимость с какого языка переводим
    # запрашиваем русские слова
    if target_word == rus_word:
        others = take_other_words(conn, cid, target_word, 'ru', OTHER_WORDS_COUNT)
        # Для английских слов добавляем гиперссылку на яндекс словарь, что бы можно было посмотреть транскрипцию
        greeting = f"Выбери перевод слова: <a href='https://translate.yandex.ru/?source_lang=en&target_lang=ru&text={translate}'>{translate}</a>"
    # запрашиваем англ слова
    else:
        others = take_other_words(conn, cid, target_word, 'en', OTHER_WORDS_COUNT)
        greeting = f"Выбери перевод слова: {translate}"

    conn.close()
    # Кнопка с правильным ответом
    target_word_btn = types.KeyboardButton(target_word)
    buttons.append(target_word_btn)
    # Кнопки с неправильными ответами
    other_words_btns = [types.KeyboardButton(word) for word in others]
    buttons.extend(other_words_btns)
    # Перемешиваем кнопки в случайном порядке
    random.shuffle(buttons)

    # Служебные кнопки:

    # Кнопка дальше
    next_btn = types.KeyboardButton(Command.NEXT)

    # Кнопка добавить слово
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)

    # Кнопка добавить случайное слово
    add_rnd_btn = types.KeyboardButton(Command.ADD_RAND_WORD)

    # Кнопка удалить слово
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)

    # Добавляем служебные кнопки в конец клавиатуры
    buttons.extend([next_btn, add_word_btn, add_rnd_btn, delete_word_btn])
    markup.add(*buttons)

    # Отправляем сообщение пользователю
    bot.send_message(message.chat.id, greeting, reply_markup=markup, parse_mode='HTML')
    bot.set_state(message.from_user.id, MyStates.check_answer, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate


@bot.message_handler(commands=['start'])
def start_command(message):
    """
    Стартовый диалог. Запрашивает имя пользователя, если пользователя нет в БД
    :param message:
    :return:
    """
    cid = message.chat.id
    conn = create_db_connection()
    # Запрашиваем имя пользователя из БД
    user_name = find_user(conn, cid)
    conn.close()
    if user_name is None:
        # Если пользователя нет в БД устанавливаем стэйт на добавление имени пользователя
        bot.set_state(message.from_user.id, MyStates.waitng_for_name, cid)
        bot.send_message(cid, "Привет, давай знакомиться. Как тебя зовут?")
    else:
        # Приветствуем пользователя и запускаем основной диалог
        bot.send_message(cid, f"Привет, {user_name[0]}!")
        main_dialog(message)


@bot.message_handler(content_types=["text"], state=MyStates.waitng_for_name)
def create_user(message):
    """
    Функция записывает нового пользователя в БД
    :param message:
    :return:
    """
    user_name = message.text
    conn = create_db_connection()
    add_user(conn, message.chat.id, user_name)
    conn.close()
    start_command(message)

# Хэндлер для кнопки Дальше или Отмена
@bot.message_handler(func=lambda message: message.text == Command.NEXT or message.text == Command.CANCEL)
def next_cards(message):
    main_dialog(message)


# Хэндлер для кнопки добавить слово
@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    cid = message.chat.id
    bot.set_state(message.from_user.id , MyStates.waitng_for_word, cid)
    bot.send_message(cid, "Введите слово.", reply_markup=types.ReplyKeyboardRemove())


# Хэндлер для кнопки добавить случайное слово
@bot.message_handler(func=lambda message: message.text == Command.ADD_RAND_WORD)
def add_rand_word(message):
    cid = message.chat.id
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=False, one_time_keyboard=True)
    markup.add(types.KeyboardButton(get_random_word()))
    markup.add(types.KeyboardButton(Command.ADD_RAND_WORD))
    markup.add(types.KeyboardButton(Command.CANCEL))
    bot.set_state(message.from_user.id, MyStates.waitng_for_word, cid)
    bot.send_message(cid, "Введите слово.", reply_markup=markup)


# Хэндлер для обработки стейта по добавлению слова в БД
@bot.message_handler(content_types=["text"], state=MyStates.waitng_for_word)
def translate_word(message):
    word = message.text
    # Получаем словарь с переводом введенного слова
    translate_dict = translate(word)

    # Если что то пошло не так с переводом
    if not translate_dict:
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=False, one_time_keyboard=True)
        markup.add(types.KeyboardButton(Command.NEXT))
        bot.reply_to(message, 'Не могу перевести слово.', reply_markup=markup)
    else:
        word_lang_code = translate_dict['translations'][0]['detectedLanguageCode']
        translated_word = translate_dict['translations'][0]['text']

        if word_lang_code == 'ru':
            ru_word = word
            en_word = translated_word
        else:
            ru_word = translated_word
            en_word = word

        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=False, one_time_keyboard=True)
        add_word_btn = types.KeyboardButton(f'Добавить пару {ru_word} - {en_word} в словарь.')
        cancel_btn = types.KeyboardButton(Command.CANCEL)
        markup.add(add_word_btn)
        markup.add(cancel_btn)
        bot.reply_to(message, f'{ru_word}-{en_word}', reply_markup=markup)
        # Устанавливаем стэйт для сохранения пары слов в БД
        bot.set_state(message.from_user.id, MyStates.save_word, message.chat.id)
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['ru_word'] = ru_word
            data['en_word'] = en_word


# Хэндлер для сохранения слов в БД
@bot.message_handler(func=lambda message: True, content_types=['text'], state=MyStates.save_word)
def save_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=False, one_time_keyboard=True)
        markup.add(types.KeyboardButton(Command.NEXT))
        if data['ru_word'] and data['en_word'] and message.chat.id:

            # Сохраняем слово в БД
            conn = create_db_connection()
            row_count = add_words(conn, message.chat.id, data['ru_word'], data['en_word'])
            conn.close()

            if row_count:
                msg = f'{row_count} cлово добавлено.'
            else:
                msg = 'Не удалось добавить слово'

            bot.reply_to(message, msg, reply_markup=markup)
            bot.delete_state(message.from_user.id, message.chat.id)


# Хэндлер для кнопки удалить слово
@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_question(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        # Если есть что удалять
        if 'translate_word' in data:
            markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=False, one_time_keyboard=True)
            del_word_btn = types.KeyboardButton(f'Удалить слово {data['translate_word']} из словаря')
            next_btn = types.KeyboardButton(Command.CANCEL)
            markup.add(del_word_btn)
            markup.add(next_btn)
            bot.send_message(message.chat.id, f'Удалить слово {data['translate_word']} из словаря?', reply_markup=markup)
            bot.set_state(message.from_user.id, MyStates.delete_word, message.chat.id)


# Хэндлер для удаления слова из БД
@bot.message_handler(func=lambda message: True, content_types=['text'], state=MyStates.delete_word)
def delete_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:

        # Если определено слово для удаления
        if 'translate_word' in data:
            markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=False, one_time_keyboard=True)
            markup.add(types.KeyboardButton(Command.NEXT))
            if data['translate_word'] and message.chat.id:
                conn = create_db_connection()
                count = del_word(conn, message.chat.id, data['translate_word'])
                conn.close()
                bot.reply_to(message, f'Удалено слов из словаря - {count}', reply_markup=markup)
                bot.delete_state(message.from_user.id, message.chat.id)


@bot.message_handler(func=lambda message: True, content_types=['text'], state=MyStates.check_answer)
def message_reply(message):
    text = message.text

    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        # print('Ответ: ', text)
        if 'target_word' in data:
            target_word = data['target_word']
            # Если ответ правильный
            if text == target_word:
                # Добавляем 1 к счетчику правильных ответов слова
                conn = create_db_connection()
                add_rigt_answer(conn, message.chat.id, target_word)
                conn.close()
                hint = show_target(data)
                hint_text = ["Отлично!❤", hint]
                next_btn = types.KeyboardButton(Command.NEXT)
                add_word_btn = types.KeyboardButton(Command.ADD_WORD)
                add_rnd_word_btn = types.KeyboardButton(Command.ADD_RAND_WORD)
                delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
                btns = []
                btns.extend([next_btn, add_word_btn, add_rnd_word_btn, delete_word_btn])
                hint = show_hint(*hint_text)
                markup = types.ReplyKeyboardMarkup(row_width=1)
                markup.add(*btns)
                bot.reply_to(message, hint, reply_markup=markup)
            else:
                # Добавляем 1 к счетчику неправильных ответов слова
                conn = create_db_connection()
                add_wrong_answer(conn, message.chat.id, target_word)
                conn.close()
                for btn in buttons:
                    if btn.text == text:
                        btn.text = text + '❌'
                        break
                hint = show_hint("Допущена ошибка!",
                                 f"Попробуй ещё раз вспомнить слово {data['translate_word']}")
                markup = types.ReplyKeyboardMarkup(row_width=2)
                markup.add(*buttons)
                bot.reply_to(message, hint, reply_markup=markup)
        else:
            main_dialog(message)


# Хэндлер с любым текстом
@bot.message_handler(content_types=["text"])
def random_text(message):
    main_dialog(message)

bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling(skip_pending=True)


