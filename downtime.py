import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from database import connect, get_current_work_shift


CATEGORIES = ("Avería", "Eléctrica", "Hidráulica", "Mecánica", "Operación", "Materiales", "Seguridad", "Clima", "Mantenimiento planificado", "Microparada")


def _parse_datetime(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(os.getenv("APP_TIMEZONE", "America/Bogota")))
    return parsed.astimezone(timezone.utc)


def downtime_dashboard(days=30, date_from=None, date_to=None, machine="", category="", status=""):
    end = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1) if date_to else datetime.now(timezone.utc)
    start = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc) if date_from else end - timedelta(days=max(1, min(int(days), 90)))
    display_end = datetime.fromisoformat(date_to).date() if date_to else end.date()
    if start >= end: raise ValueError("Rango de fechas inválido.")
    where = ["d.started_at >= %s", "d.started_at < %s"]
    params = [start, end]
    if machine: where.append("m.code=%s"); params.append(machine)
    if category: where.append("d.category=%s"); params.append(category)
    if status: where.append("d.status=%s"); params.append(status)
    clause = " AND ".join(where)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(f"""SELECT d.id,d.started_at,d.ended_at,
            CASE WHEN d.status='open' THEN extract(epoch from (CURRENT_TIMESTAMP-d.started_at))/60 ELSE d.duration_minutes END duration_minutes,
            d.category,d.cause,d.planned,d.status,d.source,d.notes,m.code machine_code,m.name machine_name,m.area,
            s.code shift_code,s.name shift_name FROM mining_downtime_events d JOIN machines m ON m.id=d.machine_id
            LEFT JOIN work_shifts s ON s.id=d.work_shift_id WHERE {clause} ORDER BY d.started_at DESC LIMIT 500""", params)
        events = cursor.fetchall()
        cursor.execute(f"""SELECT d.category,count(*) events,sum(CASE WHEN d.status='open' THEN extract(epoch from (CURRENT_TIMESTAMP-d.started_at))/60 ELSE d.duration_minutes END) minutes
            FROM mining_downtime_events d JOIN machines m ON m.id=d.machine_id WHERE {clause} GROUP BY d.category ORDER BY minutes DESC""", params)
        categories = cursor.fetchall()
        cursor.execute("SELECT code,name FROM machines WHERE active ORDER BY code")
        machines = cursor.fetchall()
    normalized = [{**event, "started_at": event["started_at"].isoformat(), "ended_at": event["ended_at"].isoformat() if event["ended_at"] else None, "duration_minutes": round(float(event["duration_minutes"]), 1)} for event in events]
    total = round(sum(event["duration_minutes"] for event in normalized), 1)
    return {"filters": {"date_from": start.date().isoformat(), "date_to": display_end.isoformat(), "machine": machine, "category": category, "status": status},
        "summary": {"total_minutes": total, "events": len(normalized), "average_minutes": round(total/max(len(normalized),1),1), "open_events": sum(e["status"]=="open" for e in normalized), "top_machine": max(normalized,key=lambda e:e["duration_minutes"])["machine_code"] if normalized else "--"},
        "events": normalized, "by_category": [{"category": row["category"], "events": row["events"], "minutes": round(float(row["minutes"]),1)} for row in categories],
        "options": {"machines": machines, "categories": list(CATEGORIES)}}


def create_downtime(machine_code, category, cause, started_at, ended_at=None, planned=False, notes=None, shift_id=None, source="manual"):
    start = _parse_datetime(started_at); end = _parse_datetime(ended_at) if ended_at else None
    if end and end <= start: raise ValueError("El fin debe ser posterior al inicio.")
    duration = (end-start).total_seconds()/60 if end else 0
    if shift_id is None:
        local_start = start.astimezone(ZoneInfo(os.getenv("APP_TIMEZONE", "America/Bogota")))
        shift = get_current_work_shift(local_start.strftime("%H:%M:%S"))
        shift_id = shift["id"] if shift else None
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id FROM machines WHERE code=%s AND active", (machine_code,)); machine = cursor.fetchone()
        if not machine: raise ValueError("Máquina no encontrada.")
        cursor.execute("""INSERT INTO mining_downtime_events(machine_id,work_shift_id,started_at,ended_at,duration_minutes,category,cause,planned,status,source,notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""", (machine["id"],shift_id,start,end,duration,category,cause,planned,"closed" if end else "open",source,notes))
        row=cursor.fetchone(); connection.commit(); return row["id"]


def close_downtime(event_id, ended_at=None):
    end = _parse_datetime(ended_at) if ended_at else datetime.now(timezone.utc)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""UPDATE mining_downtime_events SET ended_at=%s,duration_minutes=extract(epoch from (%s-started_at))/60,status='closed'
            WHERE id=%s AND status='open' AND %s>started_at RETURNING id""", (end,end,event_id,end))
        row=cursor.fetchone(); connection.commit(); return row is not None
