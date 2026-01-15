# Makefile для проекта casino_bot

# Имя Docker-образа
IMAGE_NAME = casino-bot:dev

# Порты
API_PORT = 8000
DB_PORT  = 5432

# Сборка Docker-образа
build:
	docker build -t $(IMAGE_NAME) .

# Запуск контейнеров (локально)
up:
	docker compose up --build

# Запуск контейнеров в фоне (detached)
up-detached:
	docker compose up -d --build

# Остановка и удаление контейнеров
down:
	docker compose down

# Перезапуск API без пересборки образа
restart-api:
	docker compose restart api

# Просмотр логов всех сервисов
logs:
	docker compose logs -f

# Просмотр логов API
logs-api:
	docker compose logs -f api

# Просмотр логов Postgres
logs-db:
	docker compose logs -f postgres

# Очистка неиспользуемых Docker объектов
prune:
	docker system prune -af
	docker volume prune -f

# Тестовый запуск только API без Postgres (для debug)
run-api:
	docker run --rm -p $(API_PORT):$(API_PORT) $(IMAGE_NAME)
