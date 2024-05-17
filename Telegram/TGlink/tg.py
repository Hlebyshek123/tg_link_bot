import telebot
import os
import sqlite3
from datetime import datetime
import yaml
from threading import Lock
from mcrcon import MCRcon
import multiprocessing
from multiprocessing import Process

bot = telebot.TeleBot("TOKEN")

RCON_HOST = "127.0.0.1"
RCON_PORT = 19132
RCON_PASSWORD = "12345"

kick_cmd = "kick" #команда для кика

# Пути к базам данных
db_path_minecraft = "/root/TGlink/minecraft_accounts.db"
db_path_auth = "/root/srvok/plugins/TGAuth/auth.db"
db_codes_path = "/root/TGlink/temp_codes.db"

# Инициализация блокировки
db_lock = Lock()

# Создание базы данных для аккаунтов Minecraft, если она не существует
def initialize_minecraft_db():
    conn = sqlite3.connect(db_path_minecraft)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS accounts (
                      id INTEGER PRIMARY KEY,
                      username TEXT NOT NULL,
                      tg_id TEXT NOT NULL,
                      access INTEGER
                      )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS blocked (
                      id INTEGER PRIMARY KEY,
                      username TEXT NOT NULL,
                      tg_id TEXT NOT NULL,
                      reason TEXT NOT NULL,
                      time TEXT NOT NULL
                      )''')
    conn.commit()
    conn.close()

# Функция для проверки количества привязанных аккаунтов для одного TG ID
def check_account_limit(chat_id):
    conn = sqlite3.connect(db_path_minecraft, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE tg_id = ?", (str(chat_id),))
    count = cursor.fetchone()[0]
    conn.close()
    return count < 3  # количество разрешённых Одному Челу Иметь Акков

# Функция для изменения пароля
def change_password(username, new_password):
    try:
        conn_auth = sqlite3.connect(db_path_auth)
        cursor = conn_auth.cursor()
        cursor.execute("UPDATE auth SET password = ? WHERE name = ?", (new_password, username))
        conn_auth.commit()
        conn_auth.close()
        return True
    except Exception as e:
        print(e)
        return False

# Функция для сохранения аккаунта
def save_account(username, tg_id, code):
    try:
        conn = sqlite3.connect(db_path_minecraft)
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id FROM accounts WHERE username = ?", (username,))
        result = cursor.fetchone()
        if result and result[0] != str(tg_id):
            print(f"Username {username} is already linked to another TG ID!")
            return False

        conn_temp = sqlite3.connect(db_codes_path)
        cursor_temp = conn_temp.cursor()
        cursor_temp.execute("SELECT * FROM temp_codes WHERE nickname = ? AND code = ?", (username, code))
        result = cursor_temp.fetchone()
        conn_temp.close()

        if result:
            cursor.execute("INSERT INTO accounts (username, tg_id, access) VALUES (?, ?, ?)", (username, tg_id, 0))
            conn.commit()
            conn.close()
            return True
        else:
            return False
    except Exception as e:
        print(e)
        return False

# Функция для удаления аккаунта
def remove_account(username):
    try:
        conn = sqlite3.connect(db_path_minecraft)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE username = ?", (username,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(e)

# Создание таблицы temp_codes
def create_temp_codes_table():
    conn = sqlite3.connect(db_codes_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS temp_codes (
                      id INTEGER PRIMARY KEY,
                      nickname TEXT NOT NULL,
                      code TEXT NOT NULL
                      )''')
    conn.commit()
    conn.close()

# Заполнение таблицы temp_codes данными из файла
def fill_temp_codes_table():
    codes_file_path = "/root/srvok/plugins/TGCode/codes.yml"
    try:
        with open(codes_file_path, "r") as codes_file:
            codes_data = yaml.safe_load(codes_file)
        
        conn = sqlite3.connect(db_codes_path)
        cursor = conn.cursor()

        for nickname, data in codes_data.items():
            code = data.get('code')
            cursor.execute("SELECT * FROM temp_codes WHERE nickname = ?", (nickname,))
            existing_data = cursor.fetchone()
            if not existing_data:
                cursor.execute("INSERT INTO temp_codes (nickname, code) VALUES (?, ?)", (nickname, code))

        conn.commit()
        conn.close()
    except FileNotFoundError:
        print("File with confirmation codes not found!")
    except Exception as e:
        print("Error:", e)

# Обработка команды /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🔮 | Привет! Я помогу тебе связать ник с сервера и твой тг аккаунт: напиши мне /link :D")

# Обработка команды /link
@bot.message_handler(commands=['link'])
def link_account(message):
    fill_temp_codes_table()
    chat_id = message.chat.id
    msg = bot.reply_to(message, "❤ | Отправь мне свой ник с сервера и код подтверждения через пробел (например, /link hleb_1M5QR1TQ): \n 🪄 | Ник должен быть только в нижнем регистре")
    bot.register_next_step_handler(msg, process_link_step, chat_id)

# Проверка и обработка привязки аккаунта
def process_link_step(message, chat_id):
    text = message.text.split()
    if len(text) != 2:
        bot.reply_to(message, "🚫 | Неверный формат!\n 🪄 | Используйте /link <никнейм>_<код подтверждения>\n 🪄 | Ник должен быть только в нижнем регистре")
        return
    username, code = text[1].split('_', 1)

    if not check_account_limit(chat_id):
        bot.reply_to(message, "🚫 | У вас уже привязано максимальное количество аккаунтов! (максимум 3)")
        return
    
    if save_account(username, chat_id, code):
        bot.reply_to(message, f"❤ | Твой ник {username} успешно привязан к ТГ боту! :o \n 📝 | инфо об аккаунте /mc_profile :]")
    else:
        bot.reply_to(message, "🚫 | Неверный код подтверждения или никнейм! Попробуйте снова. :'( \n 🪄 | Ник должен быть только в нижнем регистре")

# Инициализация базы данных и запуск бота
initialize_minecraft_db()
create_temp_codes_table()
fill_temp_codes_table()

@bot.message_handler(commands=['unlink'])
def unlink_account(message):
    chat_id = message.chat.id
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT username FROM accounts WHERE tg_id = ?", (str(chat_id),))
    result = cursor_minecraft.fetchall()
    if result:
        keyboard = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        for i, row in enumerate(result):
            keyboard.add(f"{i + 1}. {row[0]}")
        msg = bot.reply_to(message, "💔 | Выбери ник, который нужно отвязать от ТГ бота:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, process_unlink_step)
    else:
        bot.reply_to(message, "🚫 | Твой ник не привязан к ТГ боту :'(")
    conn_minecraft.close()

def process_unlink_step(message):
    chat_id = message.chat.id
    text = message.text.split('.')
    if len(text) != 2 or not text[0].isdigit():
        bot.reply_to(message, "🚫 | Неверный формат! выбери ник, который нужно отвязать, из предложенных вариантов.")
        return
    num = int(text[0])
    if num < 1 or num > 3:
        bot.reply_to(message, "🚫 | Неверный номер! выбери номер от 1 до 3.")
        return
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT username FROM accounts WHERE tg_id = ?", (str(chat_id),))
    result = cursor_minecraft.fetchall()
    if len(result) >= num:
        username = result[num - 1][0]
        remove_account(username)
        bot.reply_to(message, f"💔 | Твой ник {username} успешно отвязан от ТГ бота :'(")
                # Удаление клавиатуры
        bot.send_message(chat_id, "💔", reply_markup=telebot.types.ReplyKeyboardRemove())
    else:
        bot.reply_to(message, f"🚫 | Неверный номер! выбери номер от 1 до {len(result)}.")
    conn_minecraft.close()

# Путь к плагину TGplaytime на сервере Minecraft
tg_playtime_path = "/root/srvok/plugins/TGplaytime/"

# Путь к файлу last_date.yml в плагине TGplaytime на сервере Minecraft
last_date_yml_path = os.path.join(tg_playtime_path, "last_date.yml")

@bot.message_handler(commands=['mc_profile'])
def mc_profile_command(message):
    chat_id = message.chat.id
    text = message.text.split()
    if len(text) == 1:
        conn_minecraft = sqlite3.connect(db_path_minecraft)
        cursor_minecraft = conn_minecraft.cursor()
        cursor_minecraft.execute("SELECT username FROM accounts WHERE tg_id = ?", (str(chat_id),))
        result = cursor_minecraft.fetchall()
        if result:
            keyboard = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            for i, row in enumerate(result):
                keyboard.add(f"{i + 1}. {row[0]}")
            msg = bot.reply_to(message, "📃 | Выбери ник, информацию о котором хочешь посмотреть:", reply_markup=keyboard)
            bot.register_next_step_handler(msg, process_mc_profile_step)  # Changed here
        else:
            bot.reply_to(message, "🚫 | Твой ник не привязан к ТГ боту :'(")
        conn_minecraft.close()
    elif len(text) == 2 and text[1].isdigit():
        num = int(text[1])
        conn_minecraft = sqlite3.connect(db_path_minecraft)
        cursor_minecraft = conn_minecraft.cursor()
        cursor_minecraft.execute("SELECT username FROM accounts WHERE tg_id = ?", (str(chat_id),))
        result = cursor_minecraft.fetchall()
        if len(result) >= num:
            username = result[num - 1][0]
            # Путь к файлу time.yml в плагине playtime на сервере Minecraft
            time_yml_path = os.path.join(tg_playtime_path, "time.yml")
            with open(time_yml_path, 'r') as file:
                time_data = yaml.safe_load(file)
            if username in time_data:
                total_hours = time_data[username]['hour']
                total_minutes = time_data[username]['minute']
            else:
                total_hours = 0
                total_minutes = 0

            # Путь к файлу last_session.yml в плагине playtime на сервере Minecraft
            last_session_yml_path = os.path.join(tg_playtime_path, "last_session.yml")
            with open(last_session_yml_path, 'r') as file:
                last_session_data = yaml.safe_load(file)
            if username in last_session_data:
                last_session_minutes = last_session_data[username]['minutes']
                last_session_seconds = last_session_data[username]['seconds']
            else:
                last_session_minutes = 0
                last_session_seconds = 0

            # Получение даты последнего выхода из файла last_date.yml
            with open(last_date_yml_path, 'r') as file:
                last_date_data = yaml.safe_load(file)
            last_date = last_date_data.get(username, {}).get('date', 'Неизвестно')

            # Путь к файлу pureperms в плагине pureperms на сервере Minecraft
            pureperms_path = os.path.join("/root/srvok/plugins/PurePerms/players/", f"{username}.yml")
            if os.path.exists(pureperms_path):
                with open(pureperms_path, 'r') as file:
                    pureperms_data = yaml.safe_load(file)
                if 'group' in pureperms_data:
                    privilege = pureperms_data['group']
                else:
                    privilege = "Неизвестно"
            else:
                privilege = "Неизвестно"

            conn_auth = sqlite3.connect(db_path_auth)
            cursor_auth = conn_auth.cursor()
            cursor_auth.execute("SELECT ip, device, os FROM auth WHERE name = ?", (username,))
            auth_info = cursor_auth.fetchone()
            if auth_info:
                ip = auth_info[0]
                device = auth_info[1]
                oss = auth_info[2]
            else:
                ip = "Неизвестно"
                device = "Неизвестно"
                oss = "Неизвестно"

            bot.reply_to(message, f"📝 Информация по аккаунту {username}: \n\n⭐ | ТГ ID: {chat_id} \n ❤ | Привелегия: {privilege} \n 🧭 | Все наигранное время: {total_hours} ч.{total_minutes} м. \n 🕓 | Последняя сессия: {last_session_minutes} м. {last_session_seconds} с. \n 🔐 | Последний вход: \n » Дата - {last_date} \n » IP - {ip} \n » ОС - {oss} \n » Устройство - {device} \n\n 😺 | Выбери действие с аккаунтом: \n\n ✉️ | написать сообщение - /say \n 🔑 | Смена пароля - /ch_pass \n 👑 | модерация - /moderate \n 🧹 | Кикнуть аккаунт - /mc_kick \n 🖥 | снять CID защиту - /mc_cid \n 🍃 | снять SKIN защиту - /mc_skin \n 💔 | отвязать аккаунт - /unlink")
        else:
            bot.reply_to(message, "🚫 | Твой ник не привязан к ТГ боту или неверный номер привязанного аккаунта.")
        conn_minecraft.close()
    else:
        bot.reply_to(message, "🚫 | Неверный формат! используйте /mc_profile для просмотра всех привязанных аккаунтов или /mc_profile <номер_привязанного_аккаунта> для просмотра информации о конкретном аккаунте.")

def process_mc_profile_step(message):
    chat_id = message.chat.id
    text = message.text
    selected_account = None

    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT username FROM accounts WHERE tg_id = ?", (str(chat_id),))
    result = cursor_minecraft.fetchall()
    if result:
        try:
            selected_account = int(text.split('.')[0])
            if selected_account < 1 or selected_account > len(result):
                raise ValueError
        except ValueError:
            bot.reply_to(message, "🚫 | Неверный формат! выбери ник из списка.")
            return

        username = result[selected_account - 1][0]
        # Путь к файлу time.yml в плагине playtime на сервере Minecraft
        time_yml_path = os.path.join(tg_playtime_path, "time.yml")
        with open(time_yml_path, 'r') as file:
            time_data = yaml.safe_load(file)
        if username in time_data:
            total_hours = time_data[username]['hour']
            total_minutes = time_data[username]['minute']
        else:
            total_hours = 0
            total_minutes = 0

        # Путь к файлу last_session.yml в плагине playtime на сервере Minecraft
        last_session_yml_path = os.path.join(tg_playtime_path, "last_session.yml")
        with open(last_session_yml_path, 'r') as file:
            last_session_data = yaml.safe_load(file)
        if username in last_session_data:
            last_session_minutes = last_session_data[username]['minutes']
            last_session_seconds = last_session_data[username]['seconds']
        else:
            last_session_minutes = 0
            last_session_seconds = 0

        # Получение даты последнего выхода из файла last_date.yml
        with open(last_date_yml_path, 'r') as file:
            last_date_data = yaml.safe_load(file)
        last_date = last_date_data.get(username, {}).get('date', 'Неизвестно')

        # Путь к файлу pureperms в плагине pureperms на сервере Minecraft
        pureperms_path = os.path.join("/root/srvok/plugins/PurePerms/players/", f"{username}.yml")
        if os.path.exists(pureperms_path):
            with open(pureperms_path, 'r') as file:
                pureperms_data = yaml.safe_load(file)
            if 'group' in pureperms_data:
                privilege = pureperms_data['group']
            else:
                privilege = "Неизвестно"
        else:
            privilege = "Неизвестно"

        conn_auth = sqlite3.connect(db_path_auth)
        cursor_auth = conn_auth.cursor()
        cursor_auth.execute("SELECT ip, device, os FROM auth WHERE name = ?", (username,))
        auth_info = cursor_auth.fetchone()
        if auth_info:
            ip = auth_info[0]
            device = auth_info[1]
            oss = auth_info[2]
        else:
            ip = "Неизвестно"
            device = "Неизвестно"
            oss = "Неизвестно"

        bot.reply_to(message, f"📝 Информация по аккаунту {username}: \n\n ⭐ | ТГ ID: {chat_id} \n  ❤ | Привелегия: {privilege} \n 🧭 | Все наигранное время: {total_hours} ч.{total_minutes} м. \n 🕓 | Последняя сессия: {last_session_minutes} м. {last_session_seconds} с. \n 🔐 | Последний вход: \n » Дата - {last_date} \n » IP - {ip} \n » ОС - {oss} \n » Устройство - {device} \n\n 😺 | Выбери действие с аккаунтом: \n\n ✉️ | написать сообщение - /say \n 🔑 | Смена пароля - /ch_pass \n 👑 | модерация - /moderate \n 🧹 | Кикнуть аккаунт - /mc_kick \n 🖥 | снять CID защиту - /mc_cid \n 🍃 | снять SKIN защиту - /mc_skin \n 💔 | отвязать аккаунт - /unlink")

        # Удаление клавиатуры
        bot.send_message(chat_id, "✨", reply_markup=telebot.types.ReplyKeyboardRemove())
    else:
        bot.reply_to(message, "🚫 | Твой ник не привязан к ТГ боту.")
    conn_minecraft.close()


# кик С Сервера привязанного игрока
def kick_account(username):
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = mcr.command(f"{kick_cmd} {username}")
        print(response)
        return response
    except Exception as e:
        print(e)
        return str(e)

def kick_account_wrapper(username):
    result = kick_account(username)
    return result

@bot.message_handler(commands=['mc_kick'])
def mc_kick_command(message):
    chat_id = message.chat.id
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT username FROM accounts WHERE tg_id = ?", (str(chat_id),))
    result = cursor_minecraft.fetchall()
    if result:
        keyboard = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        for i, row in enumerate(result):
            keyboard.add(f"{i + 1}. {row[0]}")
        msg = bot.reply_to(message, "🧹 | Выбери ник, который нужно кикнуть с сервера:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, process_mc_kick_step)
    else:
        bot.reply_to(message, "🚫 | Твой ник не привязан к ТГ боту :'(")
    conn_minecraft.close()

def process_mc_kick_step(message):
    chat_id = message.chat.id
    text = message.text.split('.')
    if len(text) != 2 or not text[0].isdigit():
        bot.reply_to(message, "🚫 | Неверный формат! выбери ник, который нужно кикнуть, из предложенных вариантов.")
        return
    num = int(text[0])
    if num < 1 or num > 3:
        bot.reply_to(message, "🚫 | Неверный номер! выбери номер от 1 до 3.")
        return
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT username FROM accounts WHERE tg_id = ?", (str(chat_id),))
    result = cursor_minecraft.fetchall()
    if len(result) >= num:
        username = result[num - 1][0]
        p = Process(target=kick_account_wrapper, args=(username,))
        p.start()
        p.join()
        bot.reply_to(message, f"🧹 | Аккаунт {username} был успешно кикнут с сервера!")
                # Удаление клавиатуры
        bot.send_message(chat_id, "🧹", reply_markup=telebot.types.ReplyKeyboardRemove())
    else:
        bot.reply_to(message, f"🚫 | Неверный номер! выбери номер от 1 до {len(result)}.")
    conn_minecraft.close()

# Путь к плагину cid на сервере Minecraft
cid_path = "/root/srvok/plugins/TGCID/data/"

# Команда для удаления привязки к тг боту из базы данных store.db
@bot.message_handler(commands=['mc_cid'])
def mc_cid_command(message):
    chat_id = message.chat.id
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT username FROM accounts WHERE tg_id = ?", (str(chat_id),))
    result = cursor_minecraft.fetchall()
    if result:
        keyboard = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        for i, row in enumerate(result):
            keyboard.add(f"{i + 1}. {row[0]}")
        msg = bot.reply_to(message, "🖥 | Выбери ник, чтобы удалить CID защиту:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, process_mc_cid_step, result)
    else:
        bot.reply_to(message, "🚫 | Твой ник не привязан к ТГ боту :'(")
    conn_minecraft.close()

def process_mc_cid_step(message, result):
    chat_id = message.chat.id
    text = message.text.split('.')
    if len(text) != 2 or not text[0].isdigit():
        bot.reply_to(message, "🚫 | Неверный формат! выбери ник, чтобы отвязать CID защиту :o")
        return
    num = int(text[0])
    if num < 1 or num > 3:
        bot.reply_to(message, "🚫 | Неверный номер! Пожалуйста, выбери номер от 1 до 3.")
        return
    if len(result) >= num:
        username = result[num - 1][0]
        if delete_mc_cid(message, username):
            bot.reply_to(message, f"🖥 | Отвязка CID защиты аккаунта {username} прошла успешно :D")
        else:
            bot.reply_to(message, f"🚫 | Не удалось отвязать CID аккаунта {username} :[")
                    # Удаление клавиатуры
        bot.send_message(chat_id, "🪄", reply_markup=telebot.types.ReplyKeyboardRemove())
    else:
        bot.reply_to(message, f"🚫 | Неверный номер! Пожалуйста, выбери номер от 1 до {len(result)}.")

# Функция Отвязки CID из базы данных store.db
def delete_mc_cid(message, username):
    try:
        conn = sqlite3.connect(cid_path + 'store.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cid WHERE player = ?", (username,))
        result = cursor.fetchone()
        if result:
            cursor.execute("DELETE FROM cid WHERE player = ?", (username,))
            conn.commit()
            conn.close()
            return True
        else:
            bot.reply_to(message, f"🚫 | Ник {username} не привязан к CID.")
            conn.close()
            return False
    except Exception as e:
        print(e)
        return False


# смена Пароля Аккаунту
@bot.message_handler(commands=['ch_pass'])
def change_password_command(message):
    chat_id = message.chat.id
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT username FROM accounts WHERE tg_id = ?", (str(chat_id),))
    result = cursor_minecraft.fetchall()
    if result:
        keyboard = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        for i, row in enumerate(result):
            keyboard.add(f"{i + 1}. {row[0]}")
        msg = bot.reply_to(message, "🔑 | Выбери аккаунт, для которого нужно изменить пароль:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, process_change_password_step)
    else:
        bot.reply_to(message, "🚫 | Твой ник не привязан к ТГ боту :(")
    conn_minecraft.close()

def process_change_password_step(message):
    chat_id = message.chat.id
    text = message.text.split('.')
    if len(text) != 2 or not text[0].isdigit():
        bot.reply_to(message, "🚫 | Неверный формат! Выбери номер аккаунта из предложенных вариантов.")
        return
    num = int(text[0])
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT username FROM accounts WHERE tg_id = ?", (str(chat_id),))
    result = cursor_minecraft.fetchall()
    if len(result) >= num:
        username = result[num - 1][0]
        msg = bot.reply_to(message, f"🔑 | Введите новый пароль для аккаунта {username}:")
        bot.register_next_step_handler(msg, lambda m: process_change_password_confirm(m, username))
                # Удаление клавиатуры
        bot.send_message(chat_id, "🔑", reply_markup=telebot.types.ReplyKeyboardRemove())
    else:
        bot.reply_to(message, f"🚫 | Неверный номер! Выбери номер от 1 до {len(result)}.")
        
    conn_minecraft.close()

def process_change_password_confirm(message, username):
    new_password = message.text.strip()
    if change_password(username, new_password):
        bot.reply_to(message, f"🔑 | Пароль для аккаунта {username} успешно изменен на новый: {new_password}!")
    else:
        bot.reply_to(message, f"🚫 | Не удалось изменить пароль для аккаунта {username}. Попробуйте еще раз.")

# Путь к плагину skin на сервере Minecraft
skin_path = "/root/srvok/plugins/TGCID/data/"

# Команда для удаления привязки к тг боту из базы данных store.db
@bot.message_handler(commands=['mc_skin'])
def mc_skin_command(message):
    chat_id = message.chat.id
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT username FROM accounts WHERE tg_id = ?", (str(chat_id),))
    result = cursor_minecraft.fetchall()
    if result:
        keyboard = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        for i, row in enumerate(result):
            keyboard.add(f"{i + 1}. {row[0]}")
        msg = bot.reply_to(message, "🔑 | Выбери ник, чтобы удалить SKIN защиту:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, process_mc_skin_step, result)
    else:
        bot.reply_to(message, "🚫 | Твой ник не привязан к ТГ боту :'(")
    conn_minecraft.close()

def process_mc_skin_step(message, result):
    chat_id = message.chat.id
    text = message.text.split('.')
    if len(text) != 2 or not text[0].isdigit():
        bot.reply_to(message, "🚫 | Неверный формат! выбери ник, чтобы отвязать SKIN защиту :o")
        return
    num = int(text[0])
    if num < 1 or num > 3:
        bot.reply_to(message, "🚫 | Неверный номер! Пожалуйста, выбери номер от 1 до 3.")
        return
    if len(result) >= num:
        username = result[num - 1][0]
        if delete_mc_skin(message, username):
            bot.reply_to(message, f"🖥 | Отвязка SKIN защиты аккаунта {username} прошла успешно :D")
        else:
            bot.reply_to(message, f"🚫 | Не удалось отвязать SKIN аккаунта {username} :[")
                     # Удаление клавиатуры
        bot.send_message(chat_id, "👤", reply_markup=telebot.types.ReplyKeyboardRemove())
    else:
        bot.reply_to(message, f"🚫 | Неверный номер! Пожалуйста, выбери номер от 1 до {len(result)}.")

# Функция Отвязки SKIN из базы данных store.db
def delete_mc_skin(message, username):
    try:
        conn = sqlite3.connect(skin_path + 'store.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM skin WHERE player = ?", (username,))
        result = cursor.fetchone()
        if result:
            cursor.execute("DELETE FROM skin WHERE player = ?", (username,))
            conn.commit()
            conn.close()
            return True
        else:
            bot.reply_to(message, f"🚫 | Ник {username} не привязан к SKIN.")
            conn.close()
            return False
    except Exception as e:
        print(e)
        return False

# RCON

## say

@bot.message_handler(commands=['say'])
def rcon_say_command(message):
    chat_id = message.chat.id
    conn = sqlite3.connect(db_path_minecraft)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM accounts WHERE tg_id = ?", (str(chat_id),))
    result = cursor.fetchall()
    conn.close()

    if result:
        keyboard = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        for username in result:
            keyboard.add(username[0])
        msg = bot.reply_to(message, "✉️ | Выберите аккаунт, от имени которого будет отправлено сообщение:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, process_rcon_say_step)
    else:
        bot.reply_to(message, "🚫 | У вас нет привязанных аккаунтов!")
        bot.reply_to(message, "😢")

def process_rcon_say_step(message):
    chat_id = message.chat.id
    selected_account = message.text

    # Проверяем, есть ли выбранный аккаунт в базе данных
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT * FROM accounts WHERE tg_id = ? AND username = ?", (str(chat_id), selected_account))
    result = cursor_minecraft.fetchone()

    if result:
        # Проверяем, заблокирован ли выбранный ник
        cursor_minecraft.execute("SELECT reason, time FROM blocked WHERE username = ?", (selected_account,))
        block_result = cursor_minecraft.fetchone()

        if block_result:
            reason, time = block_result
            bot.reply_to(message, f"🚫 | Ваш ник {selected_account} заблокирован в консоле сервера! \n 📜 | Причина: {reason} \n 🧭 | Когда: {time}")
            bot.send_message(chat_id, "📝", reply_markup=telebot.types.ReplyKeyboardRemove())
        else:
            cursor_minecraft.execute("SELECT access FROM accounts WHERE username = ?", (selected_account,))
            access_result = cursor_minecraft.fetchone()
            conn_minecraft.close()

            if access_result and access_result[0] >= 1:
                # Показываем клавиатуру для ввода сообщения
                msg = bot.reply_to(message, "📝 | Введите сообщение для отправки на сервер:")
                bot.register_next_step_handler(msg, send_rcon_say_message, selected_account)
            else:
                bot.reply_to(message, f"🚫 | У аккаунта {selected_account} нет доступа к команде /say!")
                bot.send_message(chat_id, "📝", reply_markup=telebot.types.ReplyKeyboardRemove())
    else:
        conn_minecraft.close()
        bot.reply_to(message, "🚫 | Выбранный аккаунт не найден!")

def send_rcon_say_message(message, selected_account):
    chat_id = message.chat.id
    text = message.text

    # Отправляем RCON-сообщение на сервер Minecraft
    def send_rcon():
        try:
            with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
                resp = mcr.command(f'say {text} (by {selected_account})')
                bot.send_message(chat_id, f"📩 | Сообщение '{text}' успешно отправлено аккаунтом {selected_account} :D")
                
                bot.send_message(chat_id, "📝", reply_markup=telebot.types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(chat_id, f"🚫 | Произошла ошибка при отправке сообщения на сервер:\n\n{e}")

    # Запускаем функцию send_rcon в отдельном процессе
    p = multiprocessing.Process(target=send_rcon)
    p.start()


#moderate 

# Инициализация клавиатуры для команды /moderate
moderate_keyboard = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
moderate_keyboard.row("Забанить аккаунт", "Разбанить аккаунт")
moderate_keyboard.row("Просмотр профиля", "Бан-лист")
moderate_keyboard.row("Выдать доступ", "Забрать доступ")


@bot.message_handler(commands=['moderate'])
def moderate_command(message):
    access_level = get_access_level(message.chat.id)
    if access_level >= 3:
        bot.reply_to(message, "👑 | Выберите админ действие:", reply_markup=moderate_keyboard)
        bot.reply_to(message, f"👑")
    else:
        bot.reply_to(message, "🚫 | Недостаточно прав доступа!")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if is_linked(message.chat.id):
        access_level = get_access_level(message.chat.id)
        if message.text == "Забанить аккаунт" and access_level == 4:
            bot.reply_to(message, "🚫 | Введите никнейм пользователя, которого нужно забанить:")
            bot.register_next_step_handler(message, ban_account)
        elif message.text == "Разбанить аккаунт" and access_level == 4:
            bot.reply_to(message, "🥳 | Введите никнейм пользователя, которого нужно разбанить:")
            bot.register_next_step_handler(message, unban_account)
        elif message.text == "Просмотр профиля" and access_level >= 3:
            show_all_users(message)
        elif message.text == "Бан-лист" and access_level >= 3:
            show_ban_list(message)
        elif message.text == "Выдать доступ" and access_level == 4:
            bot.reply_to(message, "🔑 | Введите никнейм пользователя и уровень доступа (от 0 до 4) через пробел:")
            bot.register_next_step_handler(message, grant_access)
        elif message.text == "Забрать доступ" and access_level == 4:
            bot.reply_to(message, "😢 | Введите никнейм пользователя, у которого нужно забрать доступ:")
            bot.register_next_step_handler(message, revoke_access)
    else:
        bot.reply_to(message, "🚫 | Привяжите аккаунт к боту, написав /link")
    



def is_linked(tg_id):
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT * FROM accounts WHERE tg_id = ?", (str(tg_id),))
    linked = cursor_minecraft.fetchone()
    conn_minecraft.close()
    return linked is not None


def get_access_level(tg_id):
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT access FROM accounts WHERE tg_id = ?", (str(tg_id),))
    access_level = cursor_minecraft.fetchone()
    conn_minecraft.close()
    return access_level[0] if access_level else 0


def ban_account(message):
    text = message.text.strip().split()
    if len(text) < 2:
        bot.reply_to(message, "🚫 | Неверный формат! Используйте <никнейм> <причина бана>")
    
        return
    username = text[0]
    reason = ' '.join(text[1:])
    tg_id = message.chat.id
    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Блокируем пользователя
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute(
        "INSERT INTO blocked (username, tg_id, reason, time) VALUES (?, ?, ?, ?)",
        (username, str(tg_id), reason, time))
    conn_minecraft.commit()
    conn_minecraft.close()

    bot.reply_to(message,
                 f"🚫 | Аккаунт {username} заблокирован в консоли сервера по причине {reason}.")
    bot.reply_to(message, f"😶")

def unban_account(message):
    username = message.text.strip()
    tg_id = message.chat.id
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("DELETE FROM blocked WHERE username = ? AND tg_id = ?", (username, str(tg_id)))
    conn_minecraft.commit()
    conn_minecraft.close()
    bot.reply_to(message, f"✨ | Аккаунт {username} был успешно разблокирован в консоли сервера.")
    bot.reply_to(message, f"🥳")


def show_all_users(message):
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT * FROM accounts WHERE tg_id = ?", (str(message.chat.id),))
    users = cursor_minecraft.fetchall()
    conn_minecraft.close()

    response = "📁 | Пользователи бота:\n"
    for user in users:
        response += f"ТГ_ID: {user[2]} | Ник: {user[1]} | Доступ: {user[3]}\n"

    bot.reply_to(message, response)


def show_ban_list(message):
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("SELECT * FROM blocked")
    bans = cursor_minecraft.fetchall()
    conn_minecraft.close()

    response = "🚫 | Бан-лист аккаунтов:\n"
    for ban in bans:
        response += f"ТГ_ID: {ban[2]} | Ник: {ban[1]} | Причина: {ban[3]} | Время: {ban[4]}\n"

    bot.reply_to(message, response)


def grant_access(message):
    text = message.text.strip().split()
    if len(text) != 2 or not text[1].isdigit() or int(text[1]) < 0 or int(text[1]) > 4:
        bot.reply_to(message, "🚫 | Неверный формат! Используйте <никнейм> <уровень доступа от 0 до 4>")

        return
    username = text[0]
    access = int(text[1])
    # Выдаем пользователю доступ
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("UPDATE accounts SET access = ? WHERE username = ?", (access, username))
    conn_minecraft.commit()
    conn_minecraft.close()
    bot.reply_to(message, f"⭐ | Аккаунту {username} успешно выдан {access} ур. доступа!")
    bot.reply_to(message, f"✅")

def revoke_access(message):
    username = message.text.strip()
    tg_id = message.chat.id
    # Забираем доступ у пользователя
    conn_minecraft = sqlite3.connect(db_path_minecraft)
    cursor_minecraft = conn_minecraft.cursor()
    cursor_minecraft.execute("UPDATE accounts SET access = 0 WHERE username = ?", (username,))
    conn_minecraft.commit()
    conn_minecraft.close()
    bot.reply_to(message, f"⭐ | Доступ у пользователя {username} был успешно отозван.")
    bot.reply_to(message, f"✅")

# Перехватываем сообщения об ошибках при выполнении команды
@bot.message_handler(func=lambda message: True)
def error_message(message):
    bot.send_message(message.chat.id, "🚫 | Ошибка! Воспользуйтесь командой /mc_profile или /link.")

print("Бот TGlink работает!")
bot.polling()
