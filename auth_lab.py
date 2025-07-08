import requests
from dotenv import load_dotenv
import os

# 📥 Загрузка переменных из .env
load_dotenv()
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

# 📡 URL-адреса
login_url = "https://labrza.ru/api/v1/auth/login"
me_url = "https://labrza.ru/api/v1/users/me"

# 📦 Данные для авторизации в формате x-www-form-urlencoded
credentials = {
    "grant_type": "password",
    "username": username,
    "password": password
}

# 🧰 Заголовки
headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

# 🔄 Инициализируем сессию
session = requests.Session()

# 🔐 Авторизация
response = session.post(login_url, data=credentials, headers=headers)
print("🔐 Ответ на логин:", response.text)
response.raise_for_status()

# ✅ Получаем access_token
token = response.json()["access_token"]
print("✅ Токен получен:", token)

# 🔑 Добавляем заголовок авторизации
auth_headers = {
    "Authorization": f"Bearer {token}"
}
print("📡 Отправляем запрос с заголовками:", auth_headers)

# 👤 Запрашиваем информацию о пользователе
me_response = session.get(me_url, headers=auth_headers)
print("👤 Ответ сервера на /users/me:", me_response.text)
me_response.raise_for_status()

# 🖨️ Печатаем данные пользователя
print("👤 Профиль пользователя:", me_response.json())
