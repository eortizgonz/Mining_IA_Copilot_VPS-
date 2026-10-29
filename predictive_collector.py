import math
import random
from datetime import datetime, timezone

from database import connect

WEIGHTS = {"vibration": .25, "temperature": .20, "current": .17, "rpm": .14, "usage": .12, "pressure": .12}
CONDITION_LEVELS = [.72, .48, .66, .38, .57, .64, .31, .44, .27, .53]


def rule_score(ratio):
    ratio = max(0.0, ratio)
    if ratio <= .60: return 0.0
    if ratio <= .80: return (ratio - .60) / .20 * 25
    if ratio <= 1.00: return 25 + (ratio - .80) / .20 * 45
    if ratio <= 1.15: return 70 + (ratio - 1.00) / .15 * 30
    return 100.0


def bounded(value, lower, upper, decimals=2):
    return round(max(lower, min(upper, value)), decimals)


def calculate_risk(machine, values):
    ratios = {
        "usage": values["usage_hours"] / machine["max_usage_hours"],
        "vibration": values["vibration"] / machine["max_vibration"],
        "temperature": values["temperature"] / machine["max_temperature"],
        "current": values["current"] / machine["rated_current"],
        "rpm": abs(values["rpm"] - machine["nominal_rpm"]) / max(machine["nominal_rpm"], 1) / .20,
        "pressure": values["pressure"] / max(machine["max_pressure"], .01),
    }
    scores = {key: rule_score(value) for key, value in ratios.items()}
    contributions = {key: scores[key] * WEIGHTS[key] for key in scores}
    risk = sum(contributions.values())
    exceeded = sum(value >= 1 for value in ratios.values())
    if any(value >= 1.15 for value in ratios.values()): risk = max(risk, 75)
    elif exceeded >= 2: risk = max(risk, 70)
    elif exceeded == 1: risk = max(risk, 45)
    risk = round(min(99, max(1, risk)), 1)
    status = "critical" if risk >= 70 else "warning" if risk >= 40 else "healthy"
    labels = {"usage": "Horas de uso", "vibration": "Vibración", "temperature": "Temperatura", "current": "Corriente", "rpm": "Desviación de RPM", "pressure": "Presión"}
    factors = sorted(contributions, key=contributions.get, reverse=True)
    explanation = f"Factores principales: {labels[factors[0]]} ({contributions[factors[0]]:.1f} puntos) y {labels[factors[1]]} ({contributions[factors[1]]:.1f} puntos)."
    return risk, status, explanation


def next_values(machine, latest, level, rng, now):
    phase = now.timestamp() / 86400 * math.tau
    load = max(.12, min(1.08, level + math.sin(phase) * .035 + rng.gauss(0, .025)))
    if latest:
        elapsed = max(0, (now - latest["recorded_at"]).total_seconds() / 3600)
        hours = latest["usage_hours"] + elapsed
        previous = max(latest["vibration"] / machine["max_vibration"], latest["temperature"] / machine["max_temperature"])
        load = max(.12, min(1.08, previous * .72 + load * .28))
    else:
        hours = machine["max_usage_hours"] * (.30 + load * .65)
    direction = -1 if rng.random() < .5 else 1
    return {
        "usage_hours": bounded(hours, 0, machine["max_usage_hours"] * 1.15, 1),
        "vibration": bounded(machine["max_vibration"] * (.30 + load * .72) + rng.gauss(0, machine["max_vibration"] * .015), 0, machine["max_vibration"] * 1.15),
        "temperature": bounded(machine["max_temperature"] * (.42 + load * .61) + rng.gauss(0, machine["max_temperature"] * .01), 0, machine["max_temperature"] * 1.15, 1),
        "current": bounded(machine["rated_current"] * (.36 + load * .68) + rng.gauss(0, machine["rated_current"] * .012), 0, machine["rated_current"] * 1.15, 1),
        "rpm": bounded(machine["nominal_rpm"] * (1 + direction * load * .20) + rng.gauss(0, max(machine["nominal_rpm"] * .008, .1)), machine["nominal_rpm"] * .72, machine["nominal_rpm"] * 1.28, 0),
        "pressure": bounded(machine["max_pressure"] * (.34 + load * .70) + rng.gauss(0, machine["max_pressure"] * .012), 0, machine["max_pressure"] * 1.15),
    }


def append_snapshot(minimum_interval_seconds=10):
    now = datetime.now(timezone.utc)
    inserted = 0
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT * FROM machines WHERE active ORDER BY id")
        for index, machine in enumerate(cursor.fetchall()):
            cursor.execute("SELECT * FROM machine_readings WHERE machine_id=%s ORDER BY recorded_at DESC LIMIT 1", (machine["id"],))
            latest = cursor.fetchone()
            if latest and (now - latest["recorded_at"]).total_seconds() < minimum_interval_seconds:
                continue
            rng = random.Random(int(now.timestamp() // max(1, minimum_interval_seconds)) + machine["id"] * 2026)
            values = next_values(machine, latest, CONDITION_LEVELS[index % len(CONDITION_LEVELS)], rng, now)
            risk, status, explanation = calculate_risk(machine, values)
            cursor.execute("""
                INSERT INTO machine_readings
                (machine_id,recorded_at,usage_hours,vibration,temperature,current_amps,rpm,pressure,failure_probability,health_status,explanation)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (machine_id,recorded_at) DO NOTHING
            """, (machine["id"], now, values["usage_hours"], values["vibration"], values["temperature"], values["current"], values["rpm"], values["pressure"], risk, status, explanation))
            inserted += cursor.rowcount
        connection.commit()
    return inserted
