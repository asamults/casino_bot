import time
import os
import psycopg2
from psycopg2 import OperationalError

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))
DB_NAME = os.getenv("POSTGRES_DB", "casino")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

def wait_for_db(retries: int = 30, delay: int = 1) -> None:
    attempt = 0
    while attempt < retries:
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
            )
            conn.close()
            print("Postgres is ready")
            return
        except OperationalError:
            attempt += 1
            print(f"Postgres not ready, waiting {delay}s... (attempt {attempt}/{retries})")
            time.sleep(delay)
    raise RuntimeError(f"Postgres is not available after {retries} attempts")

if __name__ == "__main__":
    wait_for_db()
