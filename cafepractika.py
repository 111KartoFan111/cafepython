import telebot
import psycopg2
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# Параметры для подключения к базе данных
dbname = "cafepython"
user = "postgres"
password = "0000"
host = "127.0.0.1"
port = "5433"

# Создание экземпляра бота
bot_token = '7753531841:AAHA9Wxxh803K2fLsClKvLIPKPsgMn2VXCc'
bot = telebot.TeleBot(bot_token)

# Подключение к базе данных
def db_connect():
    return psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)

# Функция для добавления пользователя в таблицы Customers и Frequent_Customers
def add_user_if_not_exists(user_id, username):
    with db_connect() as conn:
        with conn.cursor() as cur:
            # Проверка и добавление в Customers
            cur.execute("SELECT customer_id FROM Customers WHERE customer_id = %s", (user_id,))
            if cur.fetchone() is None:
                cur.execute("INSERT INTO Customers (customer_id, name, email, phone) VALUES (%s, %s, NULL, NULL)",
                            (user_id, username))
            # Проверка и добавление в Frequent_Customers
            cur.execute("SELECT customer_id FROM Frequent_Customers WHERE customer_id = %s", (user_id,))
            if cur.fetchone() is None:
                cur.execute("INSERT INTO Frequent_Customers (customer_id, loyalty_points, visit_count, join_date, last_visit) VALUES (%s, %s, 0, NOW(), NOW())",
                            (user_id, 5000))
            conn.commit()

# Функция для получения баланса пользователя
def get_user_balance(user_id):
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT loyalty_points FROM Frequent_Customers WHERE customer_id = %s", (user_id,))
            result = cur.fetchone()
            return result[0] if result else None

# Обработчик команды /help
@bot.message_handler(commands=['help'])
def show_help(message):
    help_text = (
        "Команды бота:\n"
        "/start - Начать работу с ботом\n"
        "/balance - Проверить ваш баланс\n"
        "/category - Выбрать категорию, чтобы просмотреть доступные продукты.\n"
        "Для сотрудничества @Karto_Fan863"
    )
    bot.send_message(message.chat.id, help_text)

# Обработчик команды /balance
@bot.message_handler(commands=['balance'])
def show_balance(message):
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    if balance is not None:
        bot.send_message(message.chat.id, f"Ваш текущий баланс: {balance} баллов.")
    else:
        bot.send_message(message.chat.id, "Ваш баланс не найден. Пожалуйста, зарегистрируйтесь, используя команду /start.")

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    add_user_if_not_exists(user_id, username)
    balance = get_user_balance(user_id)
    bot.send_message(user_id, f"Добро пожаловать! У вас есть {balance} баллов. Выберите категорию продукции, чтобы начать покупку.\nДля сотрудничества @Karto_Fan863")
    show_categories(message)

@bot.message_handler(commands=['category'])
# Функция для отображения категорий
def show_categories(message):
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT category FROM Products GROUP BY category")
            categories = cur.fetchall()
            if categories:
                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                for category in categories:
                    markup.add(KeyboardButton(category[0]))
                bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=markup)
            else:
                bot.send_message(message.chat.id, "Категории отсутствуют.")

# Функция для получения всех категорий
def get_all_categories():
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT category FROM Products")
            return [row[0] for row in cur.fetchall()]

# Функция для отображения продуктов в категории с количеством на складе
def show_products_in_category(message, category):
    with db_connect() as conn:
        with conn.cursor() as cur:
            # Получаем список продуктов с их количеством на складе
            cur.execute("""
                SELECT p.name, p.price, COALESCE(i.stock_quantity, 0) AS stock_quantity
                FROM Products p
                LEFT JOIN Inventory i ON p.product_id = i.product_id
                WHERE p.category = %s
            """, (category,))
            products = cur.fetchall()
            if products:
                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                for name, price, stock_quantity in products:
                    # Отображаем только доступные продукты
                    if stock_quantity > 0:
                        markup.add(KeyboardButton(f"{name} - {price} баллов (доступно: {stock_quantity})"))
                markup.add(KeyboardButton("Назад"))
                bot.send_message(message.chat.id,f"Доступные продукты в категории {category}:",reply_markup=markup)
            else:
                bot.send_message(message.chat.id, f"В категории {category} нет доступных продуктов.")

# Обработчик выбора категории
@bot.message_handler(func=lambda message: message.text in get_all_categories())
def select_product(message):
    category = message.text
    show_products_in_category(message, category)  # Используем новую функцию

# Обработчик кнопки "Назад"
@bot.message_handler(func=lambda message: message.text == "Назад")
def go_back(message):
    show_categories(message)

# Обработчик оформления заказа
@bot.message_handler(func=lambda message: " - " in message.text)
def place_order(message):
    product_name = message.text.split(" -")[0]
    user_id = message.from_user.id

    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT loyalty_points FROM Frequent_Customers WHERE customer_id = %s", (user_id,))
            user_points = cur.fetchone()[0]
            cur.execute("SELECT price FROM Products WHERE name = %s", (product_name,))
            product_price = cur.fetchone()

            if product_price:
                product_price = product_price[0]
                if user_points >= product_price:
                    cur.execute("UPDATE Frequent_Customers SET loyalty_points = loyalty_points - %s WHERE customer_id = %s", (product_price, user_id))
                    conn.commit()
                    bot.send_message(message.chat.id, f"Заказ оформлен! Списано {product_price} баллов. Остаток баллов: {user_points - product_price}.")
                else:
                    bot.send_message(message.chat.id, "Недостаточно баллов для оформления заказа.")
            else:
                bot.send_message(message.chat.id, "Продукт не найден.")

# Запуск бота
bot.polling()
