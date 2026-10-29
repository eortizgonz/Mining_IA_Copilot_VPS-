from database import connect
from rag_service import ingest_text


PROFILES = {
    "EX-07": ("excavación y carguío", "sistema hidráulico, bombas, cilindros, corona de giro y tren de rodaje"),
    "DR-02": ("remoción de estéril", "cables, poleas, tambor, estructura, sistema de giro y accionamientos eléctricos"),
    "CT-33": ("acarreo de carbón y estéril", "motor, transmisión, frenos, suspensión, neumáticos y sistema de levante"),
    "BD-11": ("preparación de frentes", "tren de rodaje, hoja, ripper, transmisión y sistema hidráulico"),
    "PF-04": ("perforación de bancos", "cabezal rotativo, mástil, barras, compresor, avance y nivelación"),
    "TR-01": ("trituración primaria", "mandíbulas o rotor, revestimientos, rodamientos, accionamiento y alimentación"),
    "BC-12": ("transporte de carbón", "banda, empalmes, rodillos, tambores, tensor, motorreductor y raspadores"),
    "AP-02": ("apilamiento y recuperación", "pluma, cangilones, giro, traslación, cables y transportadores"),
    "CF-06": ("manejo de patios", "motor, transmisión, ejes, cucharón, articulación, frenos y sistema hidráulico"),
    "BA-03": ("desagüe de mina", "bomba, impulsor, sello, rodamientos, motor, succión y descarga"),
}

SCENARIOS = {
    "EX-07": "degradación hidráulica, holgura en giro o desgaste del tren de rodaje",
    "DR-02": "desgaste de cables/poleas, desalineación del tambor o sobrecarga del accionamiento",
    "CT-33": "sobrecarga del tren de potencia, frenos recalentados o degradación de transmisión",
    "BD-11": "desgaste del tren de rodaje, sobrecarga de hoja o pérdida hidráulica",
    "PF-04": "desgaste del cabezal, barra desalineada o sobrecarga del compresor y avance",
    "TR-01": "desgaste de revestimientos, alimentación excesiva, atasco o daño de rodamientos",
    "BC-12": "desalineación o destensado de banda, rodillo trabado o empalme degradado",
    "AP-02": "desalineación de pluma, sobrecarga de cangilones o desgaste de giro/traslación",
    "CF-06": "sobrecarga del tren de potencia, articulación con holgura o degradación hidráulica",
    "BA-03": "cavitación, obstrucción de succión, desgaste del impulsor o falla de sello/rodamiento",
}

FACTOR_GUIDANCE = {
    "Vibración": ("holgura, desalineación, lubricación deficiente o desgaste en componentes rotativos", "medir vibración axial/radial y revisar fijaciones, alineación, lubricación y rodamientos"),
    "Temperatura": ("fricción, sobrecarga, refrigeración deficiente u obstrucción", "confirmar temperatura y revisar carga, flujo, limpieza y lubricación"),
    "Corriente": ("sobrecarga, bloqueo mecánico, desbalance de fases o deterioro del accionamiento", "medir por fase y comprobar conexiones, aislamiento y libertad mecánica"),
    "Desviación de RPM": ("deslizamiento, pérdida de sincronismo, sensor inestable o transmisión degradada", "contrastar con tacómetro y revisar consigna, sensor, acople y transmisión"),
    "Presión": ("restricción, fuga, cavitación, filtro saturado o regulación defectuosa", "validar manómetro y revisar filtros, válvulas, fugas, succión y descarga"),
    "Horas de uso": ("desgaste acumulado y componentes próximos a su intervalo de intervención", "revisar historial, holguras, vida útil y planificar recambio por condición"),
}


def diagnostic_for(machine, factors, risk, status):
    process, components = PROFILES.get(machine["id"], (machine.get("machine_type", "operación minera"), "componentes críticos"))
    scenario = SCENARIOS.get(machine["id"], "degradación de componentes mecánicos, eléctricos o hidráulicos")
    levels = {
        "healthy": ("Condición estable", "Continuar operación y confirmar la tendencia en la ronda preventiva.", "Seguimiento"),
        "warning": ("Degradación incipiente", "Aumentar la frecuencia de medición y programar inspección en la próxima ventana segura.", "Planificar"),
        "critical": ("Riesgo alto de falla", "Evaluar parada controlada, aplicar LOTO y escalar a Operaciones, Mantenimiento y HSE.", "Intervenir"),
    }
    level, strategy, priority = levels[status]
    finding = f"En {process}, el patrón es compatible con {scenario}." if status != "healthy" else f"En {process}, las variables permanecen en condición estable; conservar vigilancia sobre {components}."
    causes, actions = [finding], [strategy]
    for factor in factors[:2]:
        cause, action = FACTOR_GUIDANCE[factor["label"]]
        causes.append(f"{factor['label']} ({factor['contribution']} puntos): posible {cause}.")
        actions.append(f"{priority}: {action}.")
    return {"risk_level": level, "finding": finding, "strategy": strategy, "causes": causes, "actions": actions, "source": f"MAN-MIN-{machine['id']}_mantenimiento_y_operacion.md"}


def manual_name(machine):
    return f"MAN-MIN-{machine['code']}_mantenimiento_y_operacion.md"


def manual_text(machine):
    process, components = PROFILES.get(machine["code"], (machine["machine_type"], "accionamiento, estructura y sistemas auxiliares"))
    return f"""# Manual técnico minero {machine['code']} — {machine['name']}
Área: {machine['area']}. Proceso: {process}. Componentes críticos: {components}.

## Seguridad HSE y control de energías
Solo personal competente y autorizado puede operar o intervenir el activo. Detener en zona estable, señalizar, aislar el área, aplicar bloqueo y etiquetado LOTO a todas las fuentes eléctrica, hidráulica, neumática, mecánica y gravitacional, descargar energías acumuladas y verificar energía cero. En equipos móviles aplicar freno, calzos y dispositivos de apoyo certificados. Nunca trabajar bajo cargas suspendidas, equipos elevados sin soportes, bandas en movimiento ni atmósferas no verificadas. Mantener comunicación con Control Mina.

## Límites de referencia del modelo
Horas de uso: {machine['max_usage_hours']} h. Vibración: {machine['max_vibration']} mm/s. Temperatura: {machine['max_temperature']} °C. Corriente nominal: {machine['rated_current']} A. Velocidad nominal: {machine['nominal_rpm']} rpm. Presión máxima: {machine['max_pressure']} bar. Estos valores son demostrativos; deben sustituirse o validarse con el fabricante, ingeniería de confiabilidad y las condiciones reales de la mina.

## Diagnóstico por condición
Vibración elevada: confirmar con instrumento calibrado; inspeccionar holguras, fijaciones, alineación, lubricación, rodamientos y componentes rotativos de {components}.
Temperatura elevada: validar carga, refrigeración, lubricación, fricción, obstrucciones y condición térmica.
Corriente elevada: revisar sobrecarga, bloqueo mecánico, conexiones, aislamiento, desbalance de fases y accionamiento.
Desviación de RPM: contrastar con tacómetro; revisar consigna, sensores, acoples, transmisión y deslizamiento.
Presión anormal: verificar sensor y manómetro; buscar restricciones, fugas, cavitación, filtros saturados y válvulas defectuosas.
Horas elevadas: revisar historial y vida útil de componentes; programar inspección o recambio por condición.

## Respuesta según índice de riesgo
Menor de 40 %: continuar operación, confirmar tendencia y mantener inspección preventiva.
Entre 40 % y 69.9 %: aumentar frecuencia de monitoreo y programar inspección en la próxima ventana segura.
Desde 70 %: escalar a Operaciones, Mantenimiento y HSE; evaluar parada controlada y aplicar LOTO antes de inspeccionar.

## Lista de verificación específica
Para {machine['name']} en {process}: revisar antes del turno niveles, fugas, guardas, alarmas, parada de emergencia, estructura, elementos de desgaste y el estado de {components}. Durante operación observar ruidos, olor, humo, temperatura, presión, vibración y pérdida de rendimiento. Al finalizar registrar hallazgos, horas, alarmas y orden de trabajo.

## Retorno a servicio
Cerrar la orden, retirar herramientas, reinstalar protecciones, liberar bloqueos mediante procedimiento, comprobar el área y ejecutar prueba controlada sin personal expuesto. Confirmar variables estables y obtener autorización de Operaciones y Mantenimiento.
"""


def ingest_machine_manuals():
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT * FROM machines WHERE active ORDER BY code")
        machines = cursor.fetchall()
    if not machines:
        raise ValueError("No existen máquinas activas.")
    chunks = sum(ingest_text(manual_name(machine), manual_text(machine)) for machine in machines)
    return len(machines), chunks
