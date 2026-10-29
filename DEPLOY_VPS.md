# Despliegue en Ubuntu VPS con Docker

## 1. Preparar el servidor

Instalar Docker Engine y el complemento Docker Compose. Verificar:

```bash
docker --version
docker compose version
```

Permitir el puerto elegido en el firewall, por ejemplo:

```bash
sudo ufw allow 5050/tcp
```

## 2. Descargar el proyecto

```bash
git clone URL_DEL_REPOSITORIO
cd Mining_IA_Copilot_VPS-
```

Para actualizaciones posteriores:

```bash
git pull origin main
```

## 3. Configurar secretos

```bash
cp .env.vps.example .env.vps
nano .env.vps
```

Generar una clave de sesión:

```bash
openssl rand -hex 32
```

Reemplazar `POSTGRES_PASSWORD`, el password dentro de `DATABASE_URL` y `SECRET_KEY`. La contraseña de PostgreSQL debe ser URL-safe; evitar `@`, `:`, `/`, `#` y espacios, o codificarlos para URL.

`SESSION_COOKIE_SECURE=0` permite probar por HTTP. Cambiarlo a `1` únicamente cuando el dominio funcione con HTTPS.

## 4. Validar y desplegar

```bash
docker compose --env-file .env.vps -f compose.prod.yaml config
docker compose --env-file .env.vps -f compose.prod.yaml up -d --build
```

Comprobar servicios y logs:

```bash
docker compose --env-file .env.vps -f compose.prod.yaml ps
docker compose --env-file .env.vps -f compose.prod.yaml logs -f app
docker compose --env-file .env.vps -f compose.prod.yaml logs -f collector
```

Abrir `http://IP_DEL_VPS:5050`. Crear el primer usuario desde `/register`.

## 5. Verificaciones

```bash
curl http://127.0.0.1:5050/login
curl http://127.0.0.1:5050/api/health/database
```

La base no publica el puerto 5432. Solo `app`, `collector` y `migrate` pueden acceder a PostgreSQL mediante la red interna `mining_backend`.

## 6. Operación

Actualizar:

```bash
git pull origin main
docker compose --env-file .env.vps -f compose.prod.yaml up -d --build
```

Detener sin borrar datos:

```bash
docker compose --env-file .env.vps -f compose.prod.yaml down
```

Respaldar PostgreSQL:

```bash
docker compose --env-file .env.vps -f compose.prod.yaml exec -T db pg_dump -U mining mining_ai > mining_ai_backup.sql
```

Restaurar un respaldo requiere una ventana controlada y validación previa. No ejecutar `down -v`, porque elimina el volumen persistente.
