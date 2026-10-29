import os
import random
import re
import time
from datetime import datetime, timezone

import click
from flask import Flask, flash, get_flashed_messages, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import create_user, database_status, find_user, latest_machine_readings
from predictive_collector import append_snapshot

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "development-change-this-secret"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "0") == "1",
)

PUBLIC_ENDPOINTS = {"login", "register", "static", "api_database_health"}


@app.before_request
def require_authentication():
    if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint is None or session.get("user_id"):
        return None
    if request.path.startswith("/api/"):
        return jsonify({"error": "Autenticación requerida"}), 401
    return redirect(url_for("login", next=request.path))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))
    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "")
        try:
            user = find_user(login_value)
        except Exception:
            user = None
            flash("No fue posible conectar con PostgreSQL. Verifica DATABASE_URL.", "error")
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], username=user["username"])
            return redirect(url_for("index"))
        if not any(category == "error" for category, _ in get_flashed_messages(with_categories=True)):
            flash("Usuario, correo o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        error = None
        if len(name) < 3: error = "Ingresa un nombre de al menos 3 caracteres."
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email): error = "Ingresa un correo válido."
        elif not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}", username): error = "El usuario debe tener entre 3 y 40 caracteres válidos."
        elif len(password) < 10: error = "La contraseña debe tener al menos 10 caracteres."
        elif password != confirm: error = "Las contraseñas no coinciden."
        if error:
            flash(error, "error")
        else:
            try:
                create_user(name, email, username, generate_password_hash(password))
                flash("Usuario creado correctamente. Ya puedes iniciar sesión.", "success")
                return redirect(url_for("login"))
            except ValueError as exception:
                flash(str(exception), "error")
            except Exception:
                flash("No fue posible conectar con PostgreSQL. Verifica DATABASE_URL.", "error")
    return render_template("register.html")


@app.post("/api/auth/logout")
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/auth/me")
def api_me():
    return jsonify({"id": session["user_id"], "name": session["name"], "username": session["username"]})


def question(perfil, pregunta, kpi, respuesta, accion, fuente):
    return {"perfil": perfil, "pregunta": pregunta, "kpi": kpi, "respuesta": respuesta, "accion": accion, "fuente": fuente}


QUESTIONS = [
    question("Operacional", "¿Cumplimos el plan diario de carbón ROM?", "Cumplimiento 91,8 %", "El plan está bajo presión por menor disponibilidad de la excavadora EX-07, mayor relación estéril/carbón y colas en trituración.", "Rebalancear la flota, liberar frentes y estabilizar la trituradora.", "Dispatch + SAP ERP"),
    question("Operacional", "¿Qué equipo limita la extracción?", "EX-07 · 63 %", "La excavadora EX-07 reduce el carguío por una falla hidráulica recurrente.", "Activar mantenimiento crítico y reasignar camiones.", "Telemetría + SAP PM"),
    question("Operacional", "¿Dónde está el cuello de botella?", "Trituración primaria", "Se acumula carbón ROM por detenciones cortas, sobretamaño y humedad variable.", "Controlar tamaño de alimentación y limpiar transferencias.", "SCADA + SAP MII"),
    question("Operacional", "¿Qué frente tiene menor rendimiento?", "Tajo Norte · 74 %", "El Tajo Norte presenta sobreacarreo, espera en carguío y limpieza insuficiente del techo del manto.", "Optimizar despacho y proteger la extracción selectiva.", "Dispatch + Modelo geológico"),
    question("Operacional", "¿Cómo evoluciona la relación estéril/carbón?", "6,4 bcm/t", "La relación supera el plan de 5,9 bcm/t y eleva el costo unitario.", "Priorizar prestripping y revisar la secuencia de bancos.", "Plan minero + Topografía"),
    question("Operacional", "¿Qué riesgo requiere reacción inmediata?", "Alerta CH₄ · N-3", "El metano del frente N-3 tiene tendencia ascendente, aún bajo el límite configurado.", "Restringir el área y aplicar el procedimiento HSE del sitio.", "Sensores IoT + HSE"),
    question("Mantenimiento", "¿Qué activos están críticos?", "5 activos críticos", "EX-07, banda BC-12, trituradora TR-01, camión CT-33 y apilador AP-02 requieren atención.", "Priorizar inspecciones, repuestos y contingencias.", "SAP PM + Condición"),
    question("Mantenimiento", "¿Qué falla se repite?", "Hidráulica EX-07", "La falla hidráulica se repitió tres veces este mes y afecta las toneladas cargadas.", "Ejecutar análisis de causa raíz y actualizar el preventivo.", "SAP PM"),
    question("Mantenimiento", "¿Qué repuesto es más crítico?", "Bomba EX-07", "La bomba hidráulica impacta directamente en carguío y tiene baja cobertura.", "Reservar existencias y activar la compra urgente.", "SAP MM + BTP"),
    question("Mantenimiento", "¿Qué orden debe priorizarse?", "OT-7782 urgente", "La orden de la banda BC-12 debe ejecutarse antes de detener el patio de carbón.", "Asignar cuadrilla, ventana y repuestos.", "SAP PM + SCADA"),
    question("Calidad", "¿Cumplimos la especificación comercial?", "PCI 5.850 kcal/kg", "El poder calorífico cumple, pero la humedad del Tajo Norte amenaza el límite contractual.", "Segregar el lote y mezclar con carbón de menor humedad.", "Laboratorio + LIMS"),
    question("Calidad", "¿Qué lote tiene más cenizas?", "ROM-284 · 15,2 %", "El lote supera el objetivo por contaminación con techo y piso.", "Aislar el lote y mejorar la selectividad del frente.", "LIMS + Geología"),
    question("Calidad", "¿Hay riesgo de combustión espontánea?", "Patio P-03 · medio", "La temperatura aumenta y el tiempo de residencia supera el objetivo.", "Rotar inventario y aplicar el protocolo térmico local.", "Sensores térmicos"),
    question("Calidad", "¿Qué mezcla cumple el contrato?", "Mezcla 60/40", "Una mezcla 60 % Tajo Sur y 40 % Tajo Norte cumple los parámetros estimados.", "Confirmar con muestreo y liberar la receta.", "LIMS + Blending"),
    question("Financiero", "¿Dónde se concentra la pérdida?", "USD 1,8 M/mes", "La pérdida proviene de menor carbón vendible, sobreacarreo, EX-07 y reproceso por calidad.", "Recuperar equipos y mejorar selectividad.", "SAP CO + Operación"),
    question("Financiero", "¿Cuál es el costo por tonelada ROM?", "USD 42,6/t", "Está 8,3 % sobre presupuesto por stripping, correctivos y combustible.", "Controlar estéril, ciclos y combustible.", "SAP CO"),
    question("Financiero", "¿Cuánto cuesta la indisponibilidad?", "USD 740 mil", "La indisponibilidad se concentra en trituración y carguío.", "Priorizar activos por toneladas y margen en riesgo.", "SAP CO + PM"),
    question("Financiero", "¿Cómo cerraremos el mes?", "Forecast 95,4 %", "El cierre proyectado está bajo plan por menor carbón vendible y mayor costo.", "Recuperar lotes de margen alto y contener correctivos.", "SAP Analytics Cloud"),
    question("Ejecutivo", "¿Qué riesgo exige decisión inmediata?", "4 riesgos críticos", "Los riesgos son EX-07, trituración, calidad del Tajo Norte y el plan mensual.", "Aprobar contingencias de mantenimiento, mezcla y flota.", "SAP BTP Workflow"),
    question("Ejecutivo", "¿Qué proceso destruye más valor?", "Extracción · USD 920 mil", "La extracción pierde valor por alta relación estéril/carbón, dilución y baja disponibilidad.", "Integrar secuencia, selectividad y confiabilidad.", "Plan minero + SAP CO"),
    question("Ejecutivo", "¿Cuál es la salud operacional?", "Score 73/100", "La operación está en zona amarilla por disponibilidad, calidad y costo.", "Gestionar seguridad, carbón vendible y activos restrictivos.", "Analytics + HSE"),
]

PROFILE = {
    "Operacional": {"color": "#f5b700", "titulo": "Extracción de carbón en vivo", "resumen": "Carbón ROM, descapote, stripping, carguío, acarreo, trituración y riesgos del frente.", "accion": "Liberar frentes, estabilizar trituración y recuperar el carguío.", "icono": "⛏️"},
    "Mantenimiento": {"color": "#47718d", "titulo": "Confiabilidad de flota y planta", "resumen": "Excavadoras, camiones, bandas, trituradoras, repuestos y fallas recurrentes.", "accion": "Priorizar activos por toneladas de carbón en riesgo.", "icono": "🛠️"},
    "Calidad": {"color": "#20a8b4", "titulo": "Calidad, mezcla y patios", "resumen": "Poder calorífico, cenizas, humedad, azufre, dilución, blending y combustión espontánea.", "accion": "Proteger la calidad desde el frente hasta el despacho.", "icono": "🧪"},
    "Financiero": {"color": "#b86b24", "titulo": "Costo de extracción y margen", "resumen": "Costo ROM, stripping, combustible, indisponibilidad, forecast y margen.", "accion": "Reducir sobreacarreo, dilución y correctivos.", "icono": "💰"},
    "Ejecutivo": {"color": "#6f6b84", "titulo": "Vista ejecutiva carbonífera", "resumen": "Seguridad, producción, calidad, riesgos y valor en riesgo.", "accion": "Asegurar extracción segura, continua y dentro de especificación.", "icono": "📊"},
}

PREDICTIVE_MACHINES = [
    {"id": "EX-07", "name": "Excavadora hidráulica", "area": "Extracción", "rpm_nominal": 1800, "pressure_nominal": 310},
    {"id": "DR-02", "name": "Dragalina eléctrica", "area": "Descapote", "rpm_nominal": 980, "pressure_nominal": 220},
    {"id": "CT-33", "name": "Camión minero", "area": "Acarreo", "rpm_nominal": 1900, "pressure_nominal": 260},
    {"id": "BD-11", "name": "Bulldozer", "area": "Preparación de frentes", "rpm_nominal": 1750, "pressure_nominal": 280},
    {"id": "PF-04", "name": "Perforadora rotativa", "area": "Perforación", "rpm_nominal": 1200, "pressure_nominal": 240},
    {"id": "TR-01", "name": "Trituradora primaria", "area": "Trituración", "rpm_nominal": 740, "pressure_nominal": 180},
    {"id": "BC-12", "name": "Banda transportadora", "area": "Transporte de carbón", "rpm_nominal": 1450, "pressure_nominal": 160},
    {"id": "AP-02", "name": "Apilador recuperador", "area": "Patio de carbón", "rpm_nominal": 1100, "pressure_nominal": 190},
    {"id": "CF-06", "name": "Cargador frontal", "area": "Manejo de patios", "rpm_nominal": 1850, "pressure_nominal": 275},
    {"id": "BA-03", "name": "Bomba de desagüe", "area": "Drenaje de mina", "rpm_nominal": 1750, "pressure_nominal": 210},
]

PREDICTIVE_WEIGHTS = {
    "Vibración": 25, "Temperatura": 20, "Corriente": 17,
    "Desviación de RPM": 14, "Horas de uso": 12, "Presión": 12,
}


def predictive_snapshot():
    machines = []
    for index, asset in enumerate(PREDICTIVE_MACHINES):
        severity = (index * 13 + random.randint(0, 20)) % 72
        vibration = round(2.4 + severity * 0.075 + random.uniform(-0.3, 0.3), 2)
        temperature = round(58 + severity * 0.58 + random.uniform(-2, 2), 1)
        current = round(38 + severity * 0.55 + random.uniform(-3, 3), 1)
        rpm_deviation = round(1.5 + severity * 0.12, 1)
        rpm = round(asset["rpm_nominal"] * (1 - rpm_deviation / 100))
        usage_hours = round(2100 + index * 510 + random.uniform(0, 380), 1)
        pressure = round(asset["pressure_nominal"] * (1 + (severity - 35) / 350), 1)
        scores = {
            "Vibración": min(100, max(0, (vibration - 2) / 6 * 100)),
            "Temperatura": min(100, max(0, (temperature - 55) / 50 * 100)),
            "Corriente": min(100, max(0, (current - 35) / 45 * 100)),
            "Desviación de RPM": min(100, rpm_deviation / 12 * 100),
            "Horas de uso": min(100, usage_hours / 7500 * 100),
            "Presión": min(100, abs(pressure - asset["pressure_nominal"]) / (asset["pressure_nominal"] * .16) * 100),
        }
        factors = [
            {"label": label, "score": round(score, 1), "contribution": round(score * PREDICTIVE_WEIGHTS[label] / 100, 1)}
            for label, score in scores.items()
        ]
        risk = round(sum(factor["contribution"] for factor in factors), 1)
        status = "critical" if risk >= 58 else "warning" if risk >= 38 else "healthy"
        machines.append({**asset, "vibration": vibration, "temperature": temperature, "current": current,
                         "rpm": rpm, "rpm_deviation": rpm_deviation, "usage_hours": usage_hours,
                         "pressure": pressure, "risk": risk, "status": status,
                         "factors": sorted(factors, key=lambda item: item["contribution"], reverse=True)})
    machines.sort(key=lambda item: item["risk"], reverse=True)
    return machines


def database_predictive_snapshot(rows):
    machines = []
    for row in rows:
        rpm_deviation = abs(float(row["rpm"]) - float(row["nominal_rpm"])) / max(float(row["nominal_rpm"]), 1) * 100
        scores = {
            "Vibración": min(100, float(row["vibration"]) / max(float(row["max_vibration"]), .1) * 100),
            "Temperatura": min(100, float(row["temperature"]) / max(float(row["max_temperature"]), 1) * 100),
            "Corriente": min(100, float(row["current"]) / max(float(row["rated_current"]), 1) * 100),
            "Desviación de RPM": min(100, rpm_deviation / 12 * 100),
            "Horas de uso": min(100, float(row["usage_hours"]) / max(float(row["max_usage_hours"]), 1) * 100),
            "Presión": min(100, float(row["pressure"]) / max(float(row["max_pressure"]), 1) * 100),
        }
        factors = [{"label": label, "score": round(score, 1), "contribution": round(score * PREDICTIVE_WEIGHTS[label] / 100, 1)} for label, score in scores.items()]
        machines.append({
            "id": row["id"], "name": row["name"], "area": row["area"], "machine_type": row["machine_type"],
            "recorded_at": row["recorded_at"].isoformat(), "usage_hours": float(row["usage_hours"]),
            "vibration": float(row["vibration"]), "temperature": float(row["temperature"]),
            "current": float(row["current"]), "rpm": round(float(row["rpm"])), "rpm_deviation": round(rpm_deviation, 1),
            "pressure": float(row["pressure"]), "risk": float(row["risk"]), "status": row["status"],
            "explanation": row["explanation"], "factors": sorted(factors, key=lambda item: item["contribution"], reverse=True),
        })
    return sorted(machines, key=lambda item: item["risk"], reverse=True)


def kpis():
    return {
        "cumplimiento": round(random.uniform(88, 96), 1), "disponibilidad": round(random.uniform(66, 82), 1),
        "excavadora": round(random.uniform(58, 72), 1), "trituracion": round(random.uniform(64, 80), 1),
        "flota": round(random.uniform(70, 86), 1), "calidad": round(random.uniform(86, 95), 1),
        "costo_ton": round(random.uniform(39.5, 45.8), 1), "downtime": round(random.uniform(22, 38), 1),
        "perdida": round(random.uniform(1.4, 2.2), 1), "combustible": round(random.uniform(78, 94), 1),
        "rom": random.randint(82000, 104000), "stock": random.randint(42000, 68000), "lotes_riesgo": random.randint(2, 6),
        "ordenes": random.randint(5, 13), "alertas": random.randint(8, 22), "cenizas": round(random.uniform(10.5, 15.5), 1),
        "humedad": round(random.uniform(8, 13), 1), "stripping": round(random.uniform(5.6, 6.8), 1),
        "activos_criticos": random.randint(4, 8), "score": round(random.uniform(70, 84), 1),
    }


@app.get("/")
def index(): return render_template("index.html")

@app.get("/api/kpis")
def api_kpis(): return jsonify(kpis())

@app.get("/api/profile/<perfil>")
def api_profile(perfil):
    if perfil not in PROFILE:
        return jsonify({"error": "Perfil no encontrado", "perfiles": list(PROFILE)}), 404
    return jsonify({"perfil": perfil, "info": PROFILE[perfil], "preguntas": [q for q in QUESTIONS if q["perfil"] == perfil], "kpis": kpis()})

@app.get("/api/simulator/<sim>")
def api_simulator(sim):
    simulators = {
        "ERP": {"respuesta": "Costos, inventarios, compras, repuestos y órdenes de la operación carbonífera.", "endpoint": "/sap/erp/coal/status", "datos": {"stock_carbon_t": random.randint(42000, 68000), "repuesto_critico": "Bomba EX-07"}},
        "MII": {"respuesta": "Eventos de trituración, bandas, patios, alarmas y disponibilidad.", "endpoint": "/plant/events", "datos": {"evento": "Vibración elevada BC-12", "alarmas": random.randint(8, 22)}},
        "DISPATCH": {"respuesta": "Ciclos, colas, asignación y producción por frente.", "endpoint": "/dispatch/coal-haulage", "datos": {"frente": "Tajo Norte N-3", "equipo": "EX-07"}},
        "QUALITY": {"respuesta": "Calidad, lotes, muestreo y recetas de mezcla.", "endpoint": "/quality/coal-lots", "datos": {"pci_kcal_kg": random.randint(5650, 5950), "cenizas_pct": round(random.uniform(10.5, 15.5), 1)}},
        "BTP": {"respuesta": "Workflows, aprobaciones, alertas HSE e integración cloud.", "endpoint": "/btp/workflow/coal-tasks", "datos": {"workflow": "Contingencia EX-07 y Tajo Norte", "sla": "12 horas"}},
    }
    key = sim.upper()
    if key not in simulators:
        return jsonify({"error": "Simulador no encontrado", "simuladores": list(simulators)}), 404
    return jsonify(simulators[key])

@app.get("/api/actions")
def api_actions():
    return jsonify([
        {"prioridad": "Alta", "area": "Operación", "accion": "Recuperar extracción del Tajo Norte", "responsable": "Superintendente de Mina", "color": "red"},
        {"prioridad": "Alta", "area": "Seguridad", "accion": "Verificar CH₄ y controles del frente N-3", "responsable": "Jefe HSE", "color": "yellow"},
        {"prioridad": "Alta", "area": "Mantenimiento", "accion": "Intervenir EX-07 y asegurar la bomba", "responsable": "Jefe de Mantenimiento", "color": "orange"},
        {"prioridad": "Alta", "area": "Planta", "accion": "Revisar vibración de BC-12", "responsable": "Ingeniería de Planta", "color": "blue"},
        {"prioridad": "Media", "area": "Calidad", "accion": "Segregar ROM-284 y ajustar mezcla", "responsable": "Jefe de Calidad", "color": "cyan"},
        {"prioridad": "Media", "area": "Planeamiento", "accion": "Corregir relación estéril/carbón", "responsable": "Jefe de Planeamiento", "color": "purple"},
    ])


@app.get("/api/predictive")
def api_predictive():
    database_rows = latest_machine_readings()
    machines = database_predictive_snapshot(database_rows) if database_rows else predictive_snapshot()
    source = "postgresql" if database_rows else "simulation"
    counts = {state: sum(machine["status"] == state for machine in machines) for state in ("healthy", "warning", "critical")}
    average = round(sum(machine["risk"] for machine in machines) / len(machines), 1)
    highest = machines[0]
    return jsonify({
        "machines": machines,
        "generated_at": max((machine.get("recorded_at") for machine in machines if machine.get("recorded_at")), default=datetime.now(timezone.utc).isoformat()),
        "weights": [{"label": label, "weight": weight} for label, weight in PREDICTIVE_WEIGHTS.items()],
        "summary": {**counts, "average_risk": average},
        "recommended": {
            "id": highest["id"], "name": highest["name"], "risk": highest["risk"],
            "factors": highest["factors"][:2],
            "action": "Programar inspección prioritaria y validar las señales con instrumentos y procedimientos del fabricante.",
        },
        "disclaimer": "Índice demostrativo. No sustituye diagnóstico de ingeniería, protecciones del equipo ni procedimientos HSE.",
        "source": source,
    })


@app.get("/api/health/database")
def api_database_health():
    status = database_status()
    return jsonify(status), 200 if status["connected"] or not status["configured"] else 503


@app.cli.command("capture-machine-readings")
def capture_machine_readings():
    """Inserta inmediatamente una lectura para cada máquina activa."""
    inserted = append_snapshot(minimum_interval_seconds=0)
    click.echo(f"Lecturas predictivas insertadas: {inserted}")


@app.cli.command("run-reading-collector")
@click.option("--interval-seconds", type=click.IntRange(min=10), default=lambda: int(os.getenv("PREDICTIVE_CAPTURE_INTERVAL", "900")), show_default=True)
def run_reading_collector(interval_seconds):
    """Ejecuta continuamente el colector de telemetría minera."""
    click.echo(f"Colector predictivo minero iniciado; intervalo={interval_seconds}s", err=True)
    while True:
        try:
            inserted = append_snapshot(minimum_interval_seconds=0)
            click.echo(f"{datetime.now(timezone.utc).isoformat()} · lecturas insertadas={inserted}", err=True)
        except Exception as error:
            app.logger.exception("Fallo del colector predictivo: %s", error)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5050")), debug=os.getenv("FLASK_DEBUG") == "1")
