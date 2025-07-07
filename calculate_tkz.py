import requests
import json

# 🔐 Учетные данные
username = "OutOfBorder@mail.ru"
password = "345346Tula"

# 📡 URL-адреса
login_url = "https://labrza.ru/api/v1/auth/login"
me_url = "https://labrza.ru/api/v1/users/me"
calc_url = "https://labrza.ru/api/v1/general/tkzf/calc"

# 📦 Данные для авторизации
credentials = {
    "grant_type": "password",
    "username": username,
    "password": password
}
headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

# 🔄 Сессия
session = requests.Session()

# 🔐 Авторизация
response = session.post(login_url, data=credentials, headers=headers)
print("🔐 Ответ на логин:", response.text)
response.raise_for_status()

# ✅ Токен
token = response.json()["access_token"]
print("✅ Токен получен:", token)

auth_headers = {
    "Authorization": f"Bearer {token}"
}
print("📡 Отправляем запрос с заголовками:", auth_headers)

# 👤 Проверка профиля
me_response = session.get(me_url, headers=auth_headers)
print("👤 Ответ сервера на /users/me:", me_response.text)
me_response.raise_for_status()
print("👤 Профиль пользователя:", me_response.json())

# 📤 Отправка файла model4.json
print("📡 Отправляем запрос на расчёт...")
with open("model4.json", "rb") as file:
    files = {
        "upload_file": ("model4.json", file, "application/json")
    }
    response = session.post(calc_url, headers=auth_headers, files=files)

# 📥 Результат
print("📥 Ответ сервера:", response.status_code)
print(response.text)

# 💾 Сохраняем результат
response.raise_for_status()
with open("lab_result.json", "w", encoding="utf-8") as f:
    json.dump(response.json(), f, ensure_ascii=False, indent=2)
print("✅ Результат сохранён в lab_result.json")
