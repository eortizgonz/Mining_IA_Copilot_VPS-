import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import psycopg
from dotenv import load_dotenv
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from database import run_migrations


def required(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Falta la variable {name} en .env")
    return value


def main():
    admin_password = required("POSTGRES_ADMIN_PASSWORD")
    admin_user = os.getenv("POSTGRES_ADMIN_USER", "postgres")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    target = urlparse(required("DATABASE_URL"))
    app_user = unquote(target.username or "")
    app_password = unquote(target.password or "")
    database_name = target.path.lstrip("/")
    if not all((app_user, app_password, database_name)):
        raise RuntimeError("DATABASE_URL debe incluir usuario, contraseña y base de datos")

    with psycopg.connect(host=host, port=port, dbname="postgres", user=admin_user, password=admin_password, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (app_user,))
            if cursor.fetchone():
                cursor.execute(sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(sql.Identifier(app_user), sql.Literal(app_password)))
            else:
                cursor.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(app_user), sql.Literal(app_password)))
            cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database_name,))
            if not cursor.fetchone():
                cursor.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(database_name), sql.Identifier(app_user)))

    with psycopg.connect(host=host, port=port, dbname=database_name, user=admin_user, password=admin_password, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(sql.SQL("ALTER DATABASE {} OWNER TO {}").format(sql.Identifier(database_name), sql.Identifier(app_user)))

    applied = run_migrations()
    print(f"Base {database_name} preparada correctamente.")
    print("Migraciones:", ", ".join(applied))


if __name__ == "__main__":
    main()
