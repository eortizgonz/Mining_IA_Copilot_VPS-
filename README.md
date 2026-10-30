# Coal Mining AI Copilot

Dashboard demostrativo para controlar una operación de extracción de carbón a cielo abierto.

## Alcance

- Producción de carbón ROM y cumplimiento del plan.
- Descapote y relación estéril/carbón (`bcm/t`).
- Disponibilidad de excavadoras, camiones, bandas y trituración.
- Analítica predictiva demostrativa para 10 activos, con telemetría, riesgo ponderado, filtros y factores de diagnóstico.
- Calidad: poder calorífico, cenizas, humedad y mezcla de lotes.
- Riesgos HSE, incluyendo metano y combustión espontánea.
- Costos por tonelada, indisponibilidad y pérdida estimada.
- Simulación de SAP ERP, monitoreo de planta, dispatch, laboratorio y BTP.

> Los datos son simulados. Las alertas no sustituyen los procedimientos, límites legales ni sistemas instrumentados de seguridad del sitio.

## Ejecución local

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abrir `http://127.0.0.1:5050`.

Para habilitar el depurador únicamente en desarrollo, definir `FLASK_DEBUG=1`.

## PostgreSQL

La aplicación incluye las 14 tablas del modelo suministrado, adaptadas a minería, `pgvector`, índices y datos iniciales para los 10 activos predictivos.

```bash
docker compose up --build
```

El contenedor aplica las migraciones idempotentes antes de iniciar la aplicación. Para ejecutar sin Compose, definir `DATABASE_URL`, ejecutar `python scripts/init_database.py` y después `python app.py`. Cuando existe una conexión y hay mediciones, `/api/predictive` lee PostgreSQL; sin conexión conserva el modo de simulación. El estado puede consultarse en `/api/health/database`.

La aplicación incluye registro, inicio y cierre de sesión sobre la tabla `users`. En producción se debe configurar una `SECRET_KEY` larga y aleatoria y activar `SESSION_COOKIE_SECURE=1` cuando el sitio use HTTPS.

## Colector predictivo

Captura manual para las 10 máquinas:

```bash
flask --app app capture-machine-readings
```

Colector continuo, por defecto cada 900 segundos:

```bash
flask --app app run-reading-collector --interval-seconds 900
```

La migración realiza una carga inicial idempotente en `machine_readings`: crea
una lectura para cada máquina que todavía no tenga datos. Después, el colector
inserta una nueva lectura por máquina cada 900 segundos y conserva ese intervalo
incluso si el proceso reinicia. Debe ejecutarse separado de la aplicación web.
En Docker Compose ya está definido como el servicio `collector`.

El mismo proceso registra cada 900 segundos un intervalo en
`machine_oee_readings` para cada activo: minutos planificados, minutos de
parada, toneladas objetivo, reales y conformes, disponibilidad, rendimiento,
calidad y OEE. La carga manual puede ejecutarse con:

```bash
flask --app app capture-oee-readings --interval-seconds 900
```

Estos datos son generados por reglas mientras no existan conexiones con
PLC/SCADA, Dispatch, básculas y laboratorio; por tanto no representan todavía
mediciones reales de la operación.

Cada intervalo OEE queda asociado automáticamente al turno activo usando
`APP_TIMEZONE` (por defecto `America/Bogota`). Los turnos pueden crearse,
editarse, activarse o desactivarse desde **Eficiencia OEE → Gestionar turnos**;
el dashboard y el chat permiten calcular o consultar OEE por turno.

## Documentación RAG minera

El módulo **Documentos RAG** usa PostgreSQL con pgvector y Ollama. Genera un
manual inicial para cada una de las 10 máquinas activas y permite cargar PDF,
Word, Excel, PowerPoint y documentos de texto desde la interfaz.

```bash
ollama pull nomic-embed-text
ollama pull llama3.1:8b
flask --app app ingest-machine-manuals
```

Configura `OLLAMA_BASE_URL`, `OLLAMA_EMBED_MODEL` y `OLLAMA_CHAT_MODEL` en el
entorno. En Docker sobre Linux se incluye el acceso a Ollama mediante
`host.docker.internal`.

## Despliegue en VPS

La configuración de producción está en `compose.prod.yaml`. Las instrucciones completas, secretos, actualización, logs y respaldo están documentados en [DEPLOY_VPS.md](DEPLOY_VPS.md).

```bash
cp .env.vps.example .env.vps
docker compose --env-file .env.vps -f compose.prod.yaml up -d --build
```

## Recuperación de contraseña

Configurar `APP_BASE_URL` con la URL pública y las variables `MAIL_HOST`, `MAIL_PORT`, `MAIL_USE_SSL`, `MAIL_USERNAME` y `MAIL_APP_PASSWORD`. Con Gmail se debe utilizar una contraseña de aplicación, no la contraseña normal de la cuenta. Los enlaces vencen en 30 minutos y solo pueden utilizarse una vez.
