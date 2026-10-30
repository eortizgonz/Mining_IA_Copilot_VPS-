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


def machine_risk_trends(hours=24):
    """Resume el índice de riesgo reciente por código de máquina."""
    if not database_url():
        return {}
    query = """
        SELECT m.code, count(*) AS samples,
               round(avg(r.failure_probability)::numeric, 1) AS average,
               round(min(r.failure_probability)::numeric, 1) AS minimum,
               round(max(r.failure_probability)::numeric, 1) AS maximum
        FROM machines m JOIN machine_readings r ON r.machine_id=m.id
        WHERE m.active AND r.recorded_at >= CURRENT_TIMESTAMP - (%s * interval '1 hour')
        GROUP BY m.code
    """
    try:
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute(query, (hours,))
            return {row["code"]: {"samples": row["samples"], "average": float(row["average"]), "minimum": float(row["minimum"]), "maximum": float(row["maximum"])} for row in cursor.fetchall()}
    except psycopg.Error:
        return {}


def list_work_shifts():
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT id,code,name,to_char(start_time,'HH24:MI') start_time,
            to_char(end_time,'HH24:MI') end_time,planned_minutes,active
            FROM work_shifts ORDER BY start_time,code""")
        return cursor.fetchall()


def get_current_work_shift(current_time):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT id,code,name,to_char(start_time,'HH24:MI') start_time,
            to_char(end_time,'HH24:MI') end_time,planned_minutes,active FROM work_shifts
            WHERE active AND ((start_time < end_time AND %s::time >= start_time AND %s::time < end_time)
            OR (start_time > end_time AND (%s::time >= start_time OR %s::time < end_time)))
            ORDER BY start_time DESC LIMIT 1""", (current_time, current_time, current_time, current_time))
        return cursor.fetchone()


def create_work_shift(code, name, start_time, end_time, planned_minutes, active):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""INSERT INTO work_shifts(code,name,start_time,end_time,planned_minutes,active)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING id,code,name,to_char(start_time,'HH24:MI') start_time,
            to_char(end_time,'HH24:MI') end_time,planned_minutes,active""", (code, name, start_time, end_time, planned_minutes, active))
        row = cursor.fetchone(); connection.commit(); return row


def update_work_shift(shift_id, code, name, start_time, end_time, planned_minutes, active):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""UPDATE work_shifts SET code=%s,name=%s,start_time=%s,end_time=%s,planned_minutes=%s,active=%s
            WHERE id=%s RETURNING id,code,name,to_char(start_time,'HH24:MI') start_time,
            to_char(end_time,'HH24:MI') end_time,planned_minutes,active""", (code, name, start_time, end_time, planned_minutes, active, shift_id))
        row = cursor.fetchone(); connection.commit(); return row


def delete_work_shift(shift_id):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM work_shifts WHERE id=%s RETURNING id", (shift_id,))
        row = cursor.fetchone(); connection.commit(); return row is not None


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
