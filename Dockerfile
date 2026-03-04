FROM python:3.12-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY . .

# Создание пользователя без root прав
RUN useradd -m -u 1000 nextcloud && chown -R nextcloud:nextcloud /app
USER nextcloud

# Порт для приложения
EXPOSE 9080

# Запуск
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "9080"]