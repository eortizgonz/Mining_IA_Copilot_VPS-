import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import connect, database_status, latest_machine_readings


with connect() as connection, connection.cursor() as cursor:
    for label, query in (
        ("Tablas", "SELECT count(1) AS n FROM information_schema.tables WHERE table_schema='public'"),
        ("Máquinas", "SELECT count(1) AS n FROM machines"),
        ("Lecturas", "SELECT count(1) AS n FROM machine_readings"),
        ("Usuarios", "SELECT count(1) AS n FROM users"),
    ):
        cursor.execute(query)
        print(f"{label}: {cursor.fetchone()['n']}")

status = database_status()
print("Conectada:", status["connected"])
print("Base:", status.get("database"))
print("Lecturas predictivas:", len(latest_machine_readings()))
print("Puerto app:", os.getenv("PORT", "5050"))
