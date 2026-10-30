from datetime import datetime, timedelta, timezone

from database import connect


def _clamp(value, low=0.0, high=100.0): return max(low, min(high, value))
def _status(oee): return "excellent" if oee >= 85 else "healthy" if oee >= 70 else "warning" if oee >= 60 else "critical"


def _indicators(row):
    planned, downtime = float(row["planned_minutes"] or 0), float(row["downtime_minutes"] or 0)
    target, actual, conforming = float(row["target_tons"] or 0), float(row["actual_tons"] or 0), float(row["conforming_tons"] or 0)
    availability = _clamp((planned - downtime) / planned * 100) if planned else 0
    operating_target = target * availability / 100
    performance = _clamp(actual / operating_target * 100) if operating_target else 0
    quality = _clamp(conforming / actual * 100) if actual else 0
    return tuple(round(value, 1) for value in (availability, performance, quality, availability * performance * quality / 10000))


def oee_dashboard(days=7, shift_id=None):
    days = max(1, min(int(days), 90)); period_end = datetime.now(timezone.utc); period_start = period_end - timedelta(days=days)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT m.code,m.name,m.area,COALESCE(sum(o.planned_minutes),0) planned_minutes,
            COALESCE(sum(o.downtime_minutes),0) downtime_minutes,COALESCE(sum(o.target_tons),0) target_tons,
            COALESCE(sum(o.actual_tons),0) actual_tons,COALESCE(sum(o.conforming_tons),0) conforming_tons,max(o.recorded_at) recorded_at
            FROM machines m JOIN machine_oee_readings o ON o.machine_id=m.id
            WHERE m.active AND o.recorded_at BETWEEN %s AND %s AND (%s::integer IS NULL OR o.work_shift_id=%s::integer)
            GROUP BY m.id,m.code,m.name,m.area ORDER BY m.code""", (period_start, period_end, shift_id, shift_id))
        aggregates = cursor.fetchall()
        selected_shift = None
        if shift_id:
            cursor.execute("SELECT id,code,name,to_char(start_time,'HH24:MI') start_time,to_char(end_time,'HH24:MI') end_time FROM work_shifts WHERE id=%s", (shift_id,))
            selected_shift = cursor.fetchone()
    rows = []
    for row in aggregates:
        availability, performance, quality, oee = _indicators(row)
        rows.append({"code": row["code"], "name": row["name"], "area": row["area"], "oee": oee, "availability": availability,
            "performance": performance, "quality": quality, "planned_minutes": round(float(row["planned_minutes"]), 1),
            "downtime_minutes": round(float(row["downtime_minutes"]), 1), "target_tons": round(float(row["target_tons"]), 1),
            "actual_tons": round(float(row["actual_tons"]), 1), "conforming_tons": round(float(row["conforming_tons"]), 1),
            "status": _status(oee), "recorded_at": row["recorded_at"].isoformat()})
    rows.sort(key=lambda item: item["oee"])
    totals = {key: sum(row[key] for row in rows) for key in ("planned_minutes", "downtime_minutes", "target_tons", "actual_tons", "conforming_tons")}
    availability, performance, quality, oee = _indicators(totals)
    summary = {"oee": oee, "availability": availability, "performance": performance, "quality": quality, "machines": len(rows), **{key: round(value, 1) for key, value in totals.items()}}
    return {"period_days": days, "period_start": period_start.isoformat(), "period_end": period_end.isoformat(), "shift": selected_shift, "summary": summary, "machines": rows,
        "losses": [{"category": "Paradas", "value": summary["downtime_minutes"], "unit": "min"},
            {"category": "Brecha de producción", "value": round(max(summary["target_tons"] - summary["actual_tons"], 0), 1), "unit": "t"},
            {"category": "Toneladas no conformes", "value": round(max(summary["actual_tons"] - summary["conforming_tons"], 0), 1), "unit": "t"}],
        "formula": "OEE = Disponibilidad × Rendimiento × Calidad",
        "sources": {"availability": "PostgreSQL · machine_oee_readings · minutos planificados y parada", "performance": "PostgreSQL · toneladas reales / objetivo operativo", "quality": "PostgreSQL · toneladas conformes / reales"},
        "note": "Datos persistidos por el colector de reglas. Son simulados hasta conectar PLC/SCADA, Dispatch, básculas y laboratorio; no deben presentarse como mediciones reales de mina."}
