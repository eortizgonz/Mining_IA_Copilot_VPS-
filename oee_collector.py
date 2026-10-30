import random
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from database import connect, get_current_work_shift


TARGET_TPH = {
    "excavator": 900, "dragline": 1500, "haul_truck": 240, "dozer": 500,
    "drill": 80, "crusher": 1200, "conveyor": 1500,
    "stacker_reclaimer": 1300, "wheel_loader": 600, "dewatering_pump": 500,
}


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def _status(oee):
    return "excellent" if oee >= 85 else "healthy" if oee >= 70 else "warning" if oee >= 60 else "critical"


def _values(machine, reading, interval_seconds, rng):
    interval_minutes = interval_seconds / 60
    risk = float(reading["failure_probability"])
    stop_probability = .02 if risk < 40 else .10 if risk < 70 else .25
    downtime = round(rng.uniform(2, interval_minutes) if rng.random() < stop_probability else 0, 2)
    availability = _clamp((interval_minutes - downtime) / interval_minutes * 100)
    rpm_ratio = min(float(reading["rpm"]) / max(float(machine["nominal_rpm"]), 1), max(float(machine["nominal_rpm"]), 1) / max(float(reading["rpm"]), 1))
    current_load = min(float(reading["current_amps"]) / max(float(machine["rated_current"]), 1), 1)
    performance = _clamp((rpm_ratio * .7 + current_load * .3) * 100 + rng.uniform(-1.5, 1.5))
    target_tons = TARGET_TPH.get(machine["machine_type"], 500) * interval_minutes / 60
    actual_tons = target_tons * availability / 100 * performance / 100
    quality_penalty = risk * .035
    if float(reading["temperature"]) >= float(machine["max_temperature"]): quality_penalty += 2
    if float(reading["vibration"]) >= float(machine["max_vibration"]): quality_penalty += 2
    quality = _clamp(99.5 - quality_penalty + rng.uniform(-.3, .3))
    conforming_tons = actual_tons * quality / 100
    oee = availability * performance * quality / 10000
    return {
        "interval_minutes": round(interval_minutes, 2), "planned_minutes": round(interval_minutes, 2),
        "downtime_minutes": downtime, "target_tons": round(target_tons, 2),
        "actual_tons": round(actual_tons, 2), "conforming_tons": round(conforming_tons, 2),
        "availability": round(availability, 1), "performance": round(performance, 1),
        "quality": round(quality, 1), "oee": round(oee, 1), "status": _status(oee),
        "explanation": f"Reglas: riesgo {risk:.1f}%; parada {downtime:.2f} min; rendimiento por RPM/carga; calidad penalizada por condición.",
    }


def append_oee_snapshot(interval_seconds=900, minimum_interval_seconds=None):
    minimum = interval_seconds if minimum_interval_seconds is None else minimum_interval_seconds
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(ZoneInfo(os.getenv("APP_TIMEZONE", "America/Bogota")))
    shift = get_current_work_shift(local_now.strftime("%H:%M:%S"))
    inserted = 0
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT m.*,r.failure_probability,r.health_status,r.vibration,r.temperature,r.current_amps,r.rpm
            FROM machines m JOIN LATERAL (SELECT * FROM machine_readings WHERE machine_id=m.id ORDER BY recorded_at DESC LIMIT 1) r ON true
            WHERE m.active ORDER BY m.id""")
        for machine in cursor.fetchall():
            cursor.execute("SELECT recorded_at FROM machine_oee_readings WHERE machine_id=%s ORDER BY recorded_at DESC LIMIT 1", (machine["id"],))
            latest = cursor.fetchone()
            if latest and (now - latest["recorded_at"]).total_seconds() < minimum:
                continue
            rng = random.Random(int(now.timestamp() // max(interval_seconds, 1)) + machine["id"] * 360)
            values = _values(machine, machine, interval_seconds, rng)
            cursor.execute("""INSERT INTO machine_oee_readings
                (machine_id,work_shift_id,recorded_at,interval_minutes,planned_minutes,downtime_minutes,target_tons,actual_tons,conforming_tons,availability,performance,quality,oee,status,source,explanation)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'rule_collector',%s)
                ON CONFLICT (machine_id,recorded_at) DO NOTHING""",
                (machine["id"], shift["id"] if shift else None, now, values["interval_minutes"], values["planned_minutes"], values["downtime_minutes"], values["target_tons"], values["actual_tons"], values["conforming_tons"], values["availability"], values["performance"], values["quality"], values["oee"], values["status"], values["explanation"]))
            oee_inserted = cursor.rowcount
            inserted += oee_inserted
            if oee_inserted and values["downtime_minutes"] > 0:
                risk = float(machine["failure_probability"])
                category = "Avería" if risk >= 70 else "Microparada"
                cause = f"Evento generado por reglas de condición; riesgo predictivo {risk:.1f}%."
                cursor.execute("""INSERT INTO mining_downtime_events
                    (machine_id,work_shift_id,started_at,ended_at,duration_minutes,category,cause,planned,status,source,notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,false,'closed','rule_collector',%s)""",
                    (machine["id"], shift["id"] if shift else None, now-timedelta(minutes=values["downtime_minutes"]), now,
                     values["downtime_minutes"], category, cause, "Derivada del ciclo OEE; validar contra la señal real del equipo."))
        connection.commit()
    return inserted
