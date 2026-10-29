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

El colector debe ejecutarse como proceso separado de la aplicación web. En Docker Compose ya está definido como el servicio `collector`.
