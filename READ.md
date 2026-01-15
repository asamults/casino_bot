## Casino Bot

### Run (dev)
docker compose up --build

### Reset DB
docker compose down -v
docker compose up --build

### Stack
- FastAPI
- SQLAlchemy 2.x
- psycopg v3
- Postgres 16
- Alembic
