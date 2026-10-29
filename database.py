import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))


def database_url():
    return os.getenv("DATABASE_URL", "").strip()


def connect():
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL no está configurada")
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=5)


def database_status():
    if not database_url():
        return {"configured": False, "connected": False, "message": "Modo demostración: DATABASE_URL no configurada"}
    try:
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT current_database() AS name, version() AS version")
            row = cursor.fetchone()
            return {"configured": True, "connected": True, "database": row["name"], "version": row["version"]}
    except psycopg.Error as error:
        return {"configured": True, "connected": False, "message": str(error).splitlines()[0]}


def latest_machine_readings():
    if not database_url():
        return []
    query = """
        SELECT DISTINCT ON (m.id)
            m.code AS id, m.name, m.area, m.machine_type,
            m.max_usage_hours, m.max_vibration, m.max_temperature,
            m.rated_current, m.nominal_rpm, m.max_pressure,
            r.recorded_at, r.usage_hours, r.vibration, r.temperature,
            r.current_amps AS current, r.rpm, r.pressure,
            r.failure_probability AS risk, r.health_status AS status,
            r.explanation
        FROM machines m
        JOIN machine_readings r ON r.machine_id = m.id
        WHERE m.active
        ORDER BY m.id, r.recorded_at DESC
    """
    try:
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    except psycopg.Error:
        return []


def find_user(login):
    if not database_url():
        return None
    sql = "SELECT id, name, email, username, password_hash FROM users WHERE lower(username)=lower(%s) OR lower(email)=lower(%s) LIMIT 1"
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(sql, (login, login))
        return cursor.fetchone()


def create_user(name, email, username, password_hash):
    sql = """
        INSERT INTO users (name, email, username, password_hash)
        VALUES (%s, lower(%s), lower(%s), %s)
        RETURNING id, name, email, username
    """
    try:
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, (name, email, username, password_hash))
            user = cursor.fetchone()
            connection.commit()
            return user
    except UniqueViolation as error:
        raise ValueError("El correo o nombre de usuario ya está registrado") from error


def find_user_by_email(email):
    if not database_url():
        return None
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id, name, email FROM users WHERE lower(email)=lower(%s) LIMIT 1", (email,))
        return cursor.fetchone()


def create_password_reset_token(user_id, token_hash, expires_at):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE user_id=%s AND used_at IS NULL", (user_id,))
        cursor.execute("INSERT INTO password_reset_tokens (user_id,token_hash,expires_at) VALUES (%s,%s,%s)", (user_id, token_hash, expires_at))
        connection.commit()


def password_reset_token_is_valid(token_hash):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM password_reset_tokens WHERE token_hash=%s AND used_at IS NULL AND expires_at>CURRENT_TIMESTAMP LIMIT 1", (token_hash,))
        return cursor.fetchone() is not None


def consume_password_reset_token(token_hash, password_hash):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id,user_id FROM password_reset_tokens WHERE token_hash=%s AND used_at IS NULL AND expires_at>CURRENT_TIMESTAMP FOR UPDATE", (token_hash,))
        token = cursor.fetchone()
        if not token:
            return False
        cursor.execute("UPDATE users SET password_hash=%s WHERE id=%s", (password_hash, token["user_id"]))
        cursor.execute("UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE id=%s", (token["id"],))
        connection.commit()
        return True


def run_migrations():
    sql_dir = Path(__file__).with_name("sql")
    files = sorted(sql_dir.glob("*.sql"))
    if not files:
        raise RuntimeError("No se encontraron migraciones SQL")
    with connect() as connection:
        for path in files:
            with connection.cursor() as cursor:
                cursor.execute(path.read_text(encoding="utf-8"))
        connection.commit()
    return [path.name for path in files]
