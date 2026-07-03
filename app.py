
from flask import Flask, render_template, jsonify
import random, time

app = Flask(__name__)

QUESTIONS = [
    {"perfil":"Operacional","pregunta":"¿Estamos cumpliendo el plan minero diario?","kpi":"Cumplimiento 91.8%","respuesta":"El plan minero está bajo presión por menor disponibilidad de palas, congestión en chancado primario y menor ritmo de acarreo en Rajo Norte.","accion":"Rebalancear flota, priorizar alimentación a chancado y recuperar disponibilidad de equipos críticos.","fuente":"SAP ERP + SAP MII"},
    {"perfil":"Operacional","pregunta":"¿Qué equipo está afectando más la producción?","kpi":"Pala P-07 - disponibilidad 63%","respuesta":"La Pala P-07 presenta baja disponibilidad por falla recurrente hidráulica y tiempos extendidos de mantenimiento correctivo.","accion":"Activar mantenimiento crítico, reasignar camiones y priorizar repuestos de alta criticidad.","fuente":"SAP MII + SAP ERP"},
    {"perfil":"Operacional","pregunta":"¿Dónde está el cuello de botella principal?","kpi":"Chancado primario","respuesta":"El cuello de botella está en chancado primario por acumulación de mineral, detenciones cortas y variabilidad de granulometría.","accion":"Ajustar secuencia de alimentación, controlar granulometría y activar monitoreo de eventos MII.","fuente":"SAP MII"},
    {"perfil":"Operacional","pregunta":"¿Qué orden ME está atrasada?","kpi":"ME-MIN-4421 - 58%","respuesta":"La orden ME-MIN-4421 está atrasada por detención de correa transportadora y menor disponibilidad de camiones CAEX.","accion":"Recuperar correa, reasignar flota y ajustar plan de turno.","fuente":"SAP ME"},
    {"perfil":"Operacional","pregunta":"¿Qué frente tiene menor rendimiento?","kpi":"Rajo Norte - 74%","respuesta":"Rajo Norte presenta menor rendimiento por distancia de acarreo, espera de carguío y disponibilidad limitada de equipos.","accion":"Optimizar dispatch, reducir colas y ajustar prioridad por ley de mineral.","fuente":"SAP MII + SAP CAP"},
    {"perfil":"Operacional","pregunta":"¿Qué evento de planta requiere reacción inmediata?","kpi":"Alerta MII: correa CV-12","respuesta":"La correa CV-12 presenta vibración elevada y riesgo de detención no planificada.","accion":"Activar inspección inmediata, reducir carga temporal y generar orden de mantenimiento.","fuente":"SAP MII + SAP BTP"},

    {"perfil":"Mantenimiento","pregunta":"¿Qué activos están en condición crítica?","kpi":"5 activos críticos","respuesta":"Los activos críticos son Pala P-07, Correa CV-12, Chancador CH-01, Camión CAEX-33 y Molino SAG-02.","accion":"Priorizar mantenimiento predictivo, asegurar repuestos y activar plan de contingencia operacional.","fuente":"SAP ERP + SAP MII"},
    {"perfil":"Mantenimiento","pregunta":"¿Qué falla se está repitiendo?","kpi":"Sistema hidráulico P-07","respuesta":"La falla hidráulica en Pala P-07 se ha repetido tres veces en el mes, generando pérdida de disponibilidad y producción.","accion":"Ejecutar análisis causa raíz, revisar repuestos y actualizar plan preventivo.","fuente":"SAP MII"},
    {"perfil":"Mantenimiento","pregunta":"¿Qué repuesto es más crítico?","kpi":"Bomba hidráulica P-07","respuesta":"La bomba hidráulica de P-07 es crítica por impacto directo en carguío y baja cobertura de inventario.","accion":"Reservar stock, activar compra urgente y revisar alternativas compatibles.","fuente":"SAP ERP + SAP BTP"},
    {"perfil":"Mantenimiento","pregunta":"¿Qué orden de mantenimiento debe priorizarse?","kpi":"WO-7782 urgente","respuesta":"La orden WO-7782 asociada a correa CV-12 debe priorizarse para evitar detención de chancado.","accion":"Asignar cuadrilla, ventana de intervención y repuestos antes del próximo turno.","fuente":"SAP ERP + SAP MII"},

    {"perfil":"Financiero","pregunta":"¿Dónde estamos perdiendo más dinero?","kpi":"USD 1.8M/mes","respuesta":"La mayor pérdida proviene de menor producción, downtime de chancado, baja disponibilidad de palas y consumo adicional de combustible.","accion":"Recuperar equipos críticos, reducir downtime y optimizar consumo de combustible.","fuente":"SAP ERP + SAP MII"},
    {"perfil":"Financiero","pregunta":"¿Cuál es el costo real por tonelada?","kpi":"USD 42.6/Ton","respuesta":"El costo real por tonelada está 8.3% sobre presupuesto por menor productividad, mantenimiento correctivo y energía.","accion":"Reducir correctivos, mejorar productividad por hora y controlar consumo energético.","fuente":"SAP ERP"},
    {"perfil":"Financiero","pregunta":"¿Cuánto cuesta el downtime?","kpi":"USD 740k","respuesta":"El downtime acumulado representa USD 740k, concentrado en chancado primario y disponibilidad de carguío.","accion":"Priorizar recuperación de chancado y activos de mayor impacto productivo.","fuente":"SAP ERP + SAP MII"},
    {"perfil":"Financiero","pregunta":"¿Cómo cerraremos el mes?","kpi":"Forecast 95.4%","respuesta":"El forecast mensual se proyecta en 95.4% del plan, con presión por producción menor y costos operacionales elevados.","accion":"Recuperar toneladas de alto margen y controlar gasto de mantenimiento correctivo.","fuente":"SAP ERP + SAP BTP Analytics"},

    {"perfil":"Ejecutivo","pregunta":"¿Qué riesgo requiere decisión inmediata?","kpi":"4 riesgos críticos","respuesta":"Los riesgos críticos son chancado primario, Pala P-07, correa CV-12 y cumplimiento de producción mensual.","accion":"Aprobar contingencia de mantenimiento, repuestos urgentes y redistribución de flota.","fuente":"SAP BTP Workflow"},
    {"perfil":"Ejecutivo","pregunta":"¿Qué proceso destruye más valor?","kpi":"Chancado - USD 920k","respuesta":"Chancado primario concentra la mayor destrucción de valor por detenciones, acumulación de mineral y pérdida de continuidad.","accion":"Asignar comité de recuperación, monitoreo por turno y plan de estabilización.","fuente":"SAP ERP + SAP MII"},
    {"perfil":"Ejecutivo","pregunta":"¿Qué workflow está pendiente?","kpi":"7 aprobaciones BTP","respuesta":"Hay 7 workflows pendientes: compra urgente, parada controlada, reasignación de flota, mantenimiento crítico y excepción presupuestaria.","accion":"Aprobar o reasignar responsables con SLA de 12 a 24 horas.","fuente":"SAP BTP"},
    {"perfil":"Ejecutivo","pregunta":"¿Cuál es la salud operacional del negocio?","kpi":"Score 73/100","respuesta":"El score está en zona amarilla/roja por menor disponibilidad, riesgo de chancado y costos por tonelada sobre presupuesto.","accion":"Enfocar gerencia en activos críticos, continuidad operacional y tonelaje comprometido.","fuente":"SAP BTP Analytics"},

    {"perfil":"Comercial","pregunta":"¿Estamos cumpliendo compromisos de despacho?","kpi":"OTIF 89.6%","respuesta":"El OTIF está bajo objetivo por menor producción disponible, retrasos en procesamiento y riesgo de tonelaje comprometido.","accion":"Priorizar embarques estratégicos y ajustar promesa comercial con producción real.","fuente":"SAP ERP"},
    {"perfil":"Comercial","pregunta":"¿Qué contrato está más expuesto?","kpi":"Contrato Asia Norte","respuesta":"El contrato Asia Norte está expuesto por tonelaje comprometido, ventana logística y penalidad por atraso.","accion":"Reservar producción de mayor ley y asegurar despacho prioritario.","fuente":"SAP ERP + SAP BTP"},
    {"perfil":"Comercial","pregunta":"¿Tenemos stock para cumplir embarques?","kpi":"Cobertura 86%","respuesta":"La cobertura actual permite cumplir 86% de los embarques comprometidos; el resto depende de recuperación de planta.","accion":"Priorizar mineral disponible y programar embarques parciales.","fuente":"SAP ERP + SAP CAP"},
    {"perfil":"Comercial","pregunta":"¿Podemos aceptar un nuevo compromiso comercial?","kpi":"Capacidad limitada","respuesta":"Sólo se puede aceptar si no compromete contratos existentes y si planta confirma recuperación de tonelaje.","accion":"Validar capacidad en CAP y confirmar sólo con producción asegurada.","fuente":"SAP CAP + SAP ERP"}
]

PROFILE = {
    "Operacional":{"color":"#f59e0b","titulo":"Operación Minera en Vivo","resumen":"Plan minero, carguío, acarreo, chancado, equipos críticos, órdenes ME y eventos MII.","accion":"Recuperar chancado, estabilizar Rajo Norte y mejorar disponibilidad de equipos.","icono":"⛏️"},
    "Mantenimiento":{"color":"#22c55e","titulo":"Mantenimiento y Activos Críticos","resumen":"Palas, camiones, correas, chancadores, repuestos, fallas repetitivas y mantenimiento predictivo.","accion":"Priorizar activos críticos, repuestos urgentes y mantenimiento preventivo/predictivo.","icono":"🛠️"},
    "Financiero":{"color":"#ef4444","titulo":"Finanzas, Costo y Valor Perdido","resumen":"Costo por tonelada, downtime valorizado, combustible, energía, forecast y margen.","accion":"Reducir downtime, consumo y correctivos para recuperar margen.","icono":"💰"},
    "Ejecutivo":{"color":"#8b5cf6","titulo":"Vista Ejecutiva de Riesgo Minero","resumen":"Riesgos críticos, workflows BTP, continuidad operacional, decisiones y valor en riesgo.","accion":"Aprobar contingencias y asegurar continuidad de producción mensual.","icono":"📊"},
    "Comercial":{"color":"#06b6d4","titulo":"Contratos, Embarques y OTIF","resumen":"Compromisos comerciales, embarques, stock disponible, contratos críticos y promesa comercial.","accion":"Priorizar contratos estratégicos y ajustar promesa con producción real.","icono":"🚢"}
}

def kpis():
    return {
        "cumplimiento":round(random.uniform(88,96),1),
        "oee":round(random.uniform(66,82),1),
        "pala_p07":round(random.uniform(58,72),1),
        "chancado":round(random.uniform(64,80),1),
        "flota":round(random.uniform(70,86),1),
        "otif":round(random.uniform(86,95),1),
        "costo_ton":round(random.uniform(39.5,45.8),1),
        "downtime":round(random.uniform(22,38),1),
        "perdida":round(random.uniform(1.4,2.2),1),
        "combustible":round(random.uniform(78,94),1),
        "toneladas":random.randint(82000,104000),
        "stock":random.randint(42000,68000),
        "pedidos":random.randint(3,8),
        "ordenes_me":random.randint(5,13),
        "eventos_mii":random.randint(18,36),
        "servicios_cap":random.randint(7,15),
        "workflows_btp":random.randint(4,10),
        "activos_criticos":random.randint(4,8),
        "score":round(random.uniform(70,84),1)
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/kpis")
def api_kpis():
    return jsonify(kpis())

@app.route("/api/profile/<perfil>")
def api_profile(perfil):
    return jsonify({"perfil":perfil,"info":PROFILE[perfil],"preguntas":[q for q in QUESTIONS if q["perfil"]==perfil],"kpis":kpis()})

@app.route("/api/simulator/<sim>")
def api_simulator(sim):
    sim = sim.upper()
    simulators = {
        "ERP": {"nombre":"SAP ERP Mining","respuesta":"Simulación ERP: costos, contratos, inventario de mineral, compras, repuestos, órdenes y presupuesto.","endpoint":"/sap/erp/mining/status","datos":{"stock_mineral_ton":random.randint(42000,68000),"costo_ton":"USD "+str(round(random.uniform(39.5,45.8),1)),"contrato_critico":"Asia Norte","repuesto_critico":"Bomba hidráulica P-07"}},
        "MII": {"nombre":"SAP MII Mining","respuesta":"Simulación MII: eventos de planta, chancado, correas, disponibilidad, alarmas, OEE y downtime.","endpoint":"/XMII/Illuminator?QueryTemplate=Mining/Plant/GetEvents","datos":{"evento_critico":"Vibración elevada correa CV-12","downtime_horas":round(random.uniform(22,38),1),"oee_chancado":str(round(random.uniform(64,80),1))+"%","alarmas":random.randint(18,36)}},
        "ME": {"nombre":"SAP ME Mining","respuesta":"Simulación ME: órdenes mineras, avance de producción, trazabilidad de lotes, ejecución y bloqueos operacionales.","endpoint":"/ME/api/mining-orders","datos":{"orden_critica":"ME-MIN-4421","avance":"58%","estado":"Atrasada","frente":"Rajo Norte","causa":"Correa CV-12 + flota limitada"}},
        "CAP": {"nombre":"SAP CAP Mining","respuesta":"Simulación CAP: servicios OData, reglas de priorización, dispatch, contratos, capacidad y copiloto minero.","endpoint":"/cap/odata/v4/mining","datos":{"servicio":"MiningCopilotService","entidades":["MinePlan","AssetAvailability","OreInventory","ShipmentCommitment","FinancialImpact"],"regla":"Priorizar por ley mineral + contrato + disponibilidad + costo"}},
        "BTP": {"nombre":"SAP BTP Mining","respuesta":"Simulación BTP: workflows, aprobaciones, alertas ejecutivas, integración cloud, mantenimiento crítico y analítica.","endpoint":"/btp/workflow/mining-tasks","datos":{"workflow":"Compra urgente repuesto P-07 + contingencia chancado","estado":"Pendiente aprobación","responsable":"Gerencia Operaciones","sla":"12 horas","alertas":random.randint(4,10)}}
    }
    return jsonify(simulators.get(sim, simulators["ERP"]))

@app.route("/api/actions")
def api_actions():
    return jsonify([
        {"prioridad":"Alta","area":"Operación Mina","accion":"Recuperar alimentación a chancado primario","responsable":"Superintendente Mina","color":"red"},
        {"prioridad":"Alta","area":"MII","accion":"Revisar alerta de vibración en correa CV-12","responsable":"Ingeniería de Planta","color":"blue"},
        {"prioridad":"Alta","area":"ME","accion":"Recuperar orden ME-MIN-4421","responsable":"Jefe Turno","color":"green"},
        {"prioridad":"Alta","area":"Mantenimiento","accion":"Intervenir Pala P-07 y asegurar repuesto crítico","responsable":"Jefe Mantenimiento","color":"orange"},
        {"prioridad":"Media","area":"Finanzas","accion":"Reducir costo por tonelada y downtime valorizado","responsable":"Controller","color":"yellow"},
        {"prioridad":"Alta","area":"BTP","accion":"Aprobar workflow de compra urgente y contingencia","responsable":"Gerencia Operaciones","color":"purple"},
        {"prioridad":"Media","area":"CAP","accion":"Validar reglas de priorización por ley mineral y contrato","responsable":"Arquitecto SAP","color":"pink"},
        {"prioridad":"Alta","area":"Comercial","accion":"Proteger contrato Asia Norte y embarques críticos","responsable":"Gerente Comercial","color":"cyan"}
    ])

if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000,debug=True)
