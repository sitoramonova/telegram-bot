import telebot
from secrets import secrets
import mysql.connector
from datetime import datetime, timedelta
import threading
import time

from telebot import types

token = secrets.get('BOT_API_TOKEN')
bot = telebot.TeleBot(token)

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "turbo76383876",
    "port": "3306"
}

def init_db():
    with mysql.connector.connect(**db_config) as db:
        cursor = db.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS myfirstdatabase")
        db.commit()

    db_config["database"] = "myfirstdatabase"
    with mysql.connector.connect(**db_config) as db:
        cursor = db.cursor()
        cursor.execute("DROP TABLE IF EXISTS tasks")  # Drop table if exists to create a new one
        cursor.execute("""
            CREATE TABLE tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                description VARCHAR(255),
                deadline DATETIME,
                completed BOOLEAN DEFAULT FALSE
            )
        """)
        db.commit()

init_db()

user_states = {}

@bot.message_handler(commands=['add'])
def add_task(message):
    user_states[message.chat.id] = 'waiting_for_description'
    bot.send_message(message.chat.id, "Введите описание задачи:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_for_description')
def get_task_description(message):
    task_description = message.text
    user_states[message.chat.id] = {'state': 'waiting_for_deadline', 'description': task_description}
    bot.send_message(message.chat.id, "Введите дедлайн задачи (в формате ДД.ММ.ГГГГ ЧЧ:ММ):")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('state') == 'waiting_for_deadline')
def get_task_deadline(message):
    try:
        deadline = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        user_id = message.chat.id
        task_description = user_states[user_id]['description']

        with mysql.connector.connect(**db_config) as db:
            cursor = db.cursor()
            sql = "INSERT INTO tasks (user_id, description, deadline) VALUES (%s, %s, %s)"
            cursor.execute(sql, (user_id, task_description, deadline))
            db.commit()

        bot.send_message(
            message.chat.id,
            f"Задача '{task_description}' с дедлайном {deadline.strftime('%d.%m.%Y %H:%M')} успешно добавлена!"
        )

        reminder_time = deadline - timedelta(days=1)
        threading.Thread(target=reminder, args=(user_id, task_description, reminder_time)).start()

        user_states.pop(user_id)

    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат даты. Пожалуйста, попробуйте снова.")
    except mysql.connector.Error as db_err:
        bot.send_message(message.chat.id, f"Ошибка базы данных: {db_err}")

def reminder(user_id, task_description, reminder_time):
    time_to_wait = (reminder_time - datetime.now()).total_seconds()
    if time_to_wait > 0:
        time.sleep(time_to_wait)
    bot.send_message(user_id, f"Напоминание: задача '{task_description}' должна быть выполнена завтра!")

@bot.message_handler(commands=['tasks'])
def show_tasks(message):
    user_id = message.chat.id
    with mysql.connector.connect(**db_config) as db:
        cursor = db.cursor()
        cursor.execute("SELECT id, description, deadline FROM tasks WHERE user_id = %s AND completed = FALSE", (user_id,))
        tasks = cursor.fetchall()

    if tasks:
        response = "Ваши задачи:\n"
        for idx, (task_id, description, deadline) in enumerate(tasks, 1):
            response += f"{idx}. {description} - дедлайн: {deadline.strftime('%d.%m.%Y %H:%M')} (ID: {task_id})\n"
        bot.send_message(message.chat.id, response)
    else:
        bot.send_message(message.chat.id, "У вас нет невыполненных задач.")

@bot.message_handler(commands=['complete'])
def complete_task(message):
    bot.send_message(message.chat.id, "Введите ID задачи, которую хотите отметить как выполненную:")

@bot.message_handler(func=lambda message: message.text.isdigit())
def mark_task_completed(message):
    task_id = int(message.text)
    user_id = message.chat.id

    with mysql.connector.connect(**db_config) as db:
        cursor = db.cursor()
        cursor.execute("UPDATE tasks SET completed = TRUE WHERE id = %s AND user_id = %s", (task_id, user_id))
        db.commit()

    if cursor.rowcount > 0:
        bot.send_message(message.chat.id, f"Задача с ID {task_id} отмечена как выполненная.")
    else:
        bot.send_message(message.chat.id, "Задача не найдена или уже выполнена.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "👩‍💻 Что может бот?":
        bot.send_message(
            message.chat.id,
            "Этот бот поможет управлять задачами. \nТы можешь записать свою задачу и указать дедлайн ее выполнения. За сутки до него тебе придет уведомление. Как только ты выполнишь свою задачу, укажи это тут. Также ты можешь посмотреть список невыполненных задач."
        )
    elif message.text == "🩰 Начать":
        bot.send_message(
            message.chat.id,
            "Выберите одну из команд: \n /add - добавить задачу \n /tasks - посмотреть текущие задачи \n /complete - отметить задачу как выполненную"
        )

if __name__ == '__main__':
    bot.polling(none_stop=True)
