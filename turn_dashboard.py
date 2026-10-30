import os
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from database import connect, get_current_work_shift


def _shift_window(shift, local_now, zone):
    start_time = time.fromisoformat(shift["start_time"])
    end_time = time.fromisoformat(shift["end_time"])
    start = datetime.combine(local_now.date(), start_time, zone)
    end = datetime.combine(local_now.date(), end_time, zone)
    if end <= start:
        end += timedelta(days=1)
        if local_now.time() < end_time:
            start -= timedelta(days=1)
            end -= timedelta(days=1)
    return start, end


def turn_dashboard():
    zone = ZoneInfo(os.getenv("APP_TIMEZONE", "America/Bogota"))
    local_now = datetime.now(zone)
    shift = get_current_work_shift(local_now.strftime("%H:%M:%S"))
    if not shift:
        return {"active": False, "generated_at": local_now.isoformat(), "message": "No hay un turno activo para la hora actual."}
    start, end = _shift_window(shift, local_now, zone)
    start_utc, now_utc = start.astimezone(timezone.utc), local_now.astimezone(timezone.utc)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT coalesce(sum(target_tons),0) target,coalesce(sum(actual_tons),0) actual,
            coalesce(sum(conforming_tons),0) conforming,coalesce(sum(downtime_minutes),0) downtime,
            coalesce(avg(availability),0) availability,coalesce(avg(performance),0) performance,
            coalesce(avg(quality),0) quality,coalesce(avg(oee),0) oee,coalesce(sum(interval_minutes),0) intervals
            FROM machine_oee_readings WHERE work_shift_id=%s AND recorded_at >= %s AND recorded_at <= %s""",
            (shift["id"], start_utc, now_utc))
        summary = cursor.fetchone()
        cursor.execute("""SELECT date_trunc('hour',recorded_at AT TIME ZONE %s) bucket,
            coalesce(sum(target_tons),0) target,coalesce(sum(actual_tons),0) actual
            FROM machine_oee_readings WHERE work_shift_id=%s AND recorded_at >= %s AND recorded_at <= %s
            GROUP BY 1 ORDER BY 1""", (str(zone), shift["id"], start_utc, now_utc))
        hourly_rows = cursor.fetchall()
        cursor.execute("""SELECT m.code,m.name,r.failure_probability,r.health_status
            FROM machines m JOIN LATERAL (SELECT failure_probability,health_status FROM machine_readings
            WHERE machine_id=m.id ORDER BY recorded_at DESC LIMIT 1) r ON true
            WHERE m.active ORDER BY r.failure_probability DESC LIMIT 3""")
        risks = cursor.fetchall()
        cursor.execute("""SELECT count(*) open_events FROM mining_downtime_events
            WHERE work_shift_id=%s AND status='open'""", (shift["id"],))
        open_events = cursor.fetchone()["open_events"]
    elapsed_minutes = max((local_now - start).total_seconds() / 60, 1)
    planned_minutes = float(shift["planned_minutes"])
    observed_target = float(summary["target"])
    actual = float(summary["actual"])
    # El plan total extrapola la tasa objetivo observada al horario completo del turno.
    target_rate = observed_target / max(elapsed_minutes / 60, .01)
    plan = target_rate * planned_minutes / 60
    if not observed_target:
        plan = actual = target_rate = 0
    completion = actual / plan * 100 if plan else 0
    actual_rate = actual / max(elapsed_minutes / 60, .01)
    remaining = max(plan - actual, 0)
    projected = local_now + timedelta(hours=remaining / actual_rate) if actual_rate > 0 else None
    hourly = [{"hour": row["bucket"].strftime("%Hh"), "plan": round(float(row["target"]), 1), "actual": round(float(row["actual"]), 1)} for row in hourly_rows]
    alerts = []
    for risk in risks:
        probability = float(risk["failure_probability"])
        if probability >= 38:
            alerts.append({"level": "critical" if probability >= 58 else "warning", "title": f"{risk['code']} · {risk['name']}", "detail": f"Riesgo predictivo {probability:.1f}% ({risk['health_status']})."})
    if open_events:
        alerts.insert(0, {"level": "critical", "title": f"{open_events} parada(s) abierta(s)", "detail": "Requieren cierre o seguimiento durante el turno."})
    return {
        "active": True, "generated_at": local_now.isoformat(),
        "context": {"operation": "Mina de carbón", "area": "Extracción y manejo ROM", "fleet": "10 activos", "shift": f"{shift['name']} · {shift['start_time']}–{shift['end_time']}", "product": "Carbón ROM", "source": "Colector OEE"},
        "shift": {"id": shift["id"], "code": shift["code"], "name": shift["name"], "start": shift["start_time"], "end": shift["end_time"],
                  "plan_tons": round(plan, 1), "actual_tons": round(actual, 1), "conforming_tons": round(float(summary["conforming"]), 1),
                  "completion_pct": round(completion, 1), "rate_tph": round(actual_rate, 1), "target_rate_tph": round(target_rate, 1),
                  "projected_end": projected.strftime("%H:%M") if projected else "--", "target_end": shift["end_time"]},
        "oee": {key: round(float(summary[key]), 1) for key in ("oee", "availability", "performance", "quality")},
        "hourly": hourly, "alerts": alerts,
        "state": {"highest_risk_machine": risks[0]["code"] if risks else "--", "risk": round(float(risks[0]["failure_probability"]), 1) if risks else 0,
                  "downtime_minutes": round(float(summary["downtime"]), 1), "open_events": open_events,
                  "conforming_tons": round(float(summary["conforming"]), 1)},
        "note": "Indicadores calculados con machine_oee_readings del turno activo. Las toneladas y paradas del colector son proxies demostrativos hasta conectar señales reales.",
    }
