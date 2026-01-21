# Casino Bot Project

## Описание
**Casino Bot** — программное обеспечение на Python для управления игровой платформой с административными и аналитическими функциями. Проект использует современный стек: FastAPI для API, PostgreSQL для хранения данных и Alembic для управления миграциями базы данных.  

Цель проекта — обеспечить безопасное и масштабируемое управление игровыми сессиями, пользователями и аналитикой.

---

## Структура проекта

casino_bot/
├── app/
│ ├── api/ # REST API endpoints
│ ├── core/ # Основная логика приложения
│ ├── db/ # Модели, схемы, миграции
│ ├── services/ # Сервисы бизнес-логики
│ └── main.py # Точка входа приложения
├── alembic/ # Миграции базы данных
├── tests/ # Юнит-тесты
├── .venv/ # Виртуальное окружение
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md


## Установка

### Локальная установка
1. Клонировать репозиторий:
```bash
git clone https://github.com/asamults/casino_bot.git
cd casino_bot

    Создать виртуальное окружение и активировать:

python3 -m venv .venv
source .venv/bin/activate

    Установить зависимости:

pip install -r requirements.txt

    Настроить переменные окружения:

export DATABASE_URL=postgresql://user:password@localhost:5432/casino
export SECRET_KEY='your-secret-key'

Миграции базы данных

Используется Alembic:

# Инициализация миграций (один раз)
alembic init alembic

# Создание новой миграции
alembic revision --autogenerate -m "Описание изменений"

# Применение миграций
alembic upgrade head

# Откат миграций (rollback)
alembic downgrade -1

Запуск проекта
Локальный запуск
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


Доступ к административным эндпоинтам:

http://127.0.0.1:8000/admin

Docker
docker-compose up --build

Тестирование
pytest tests/ --cov=app

Лицензия

MIT License. Все компоненты проекта могут использоваться и модифицироваться в соответствии с условиями лицензии.