# Sistema de reservas del laboratorio

API HTTP local para consultar disponibilidad, reservar y cancelar equipos de laboratorio
sin perder el historial. Implementa el contrato congelado de
[`docs/spec.md`](docs/spec.md) v1.0.0. Las decisiones y sus motivos están en
[`docs/decisions.md`](docs/decisions.md).

## Requisitos

Python 3.11 o superior. Dependencias fijadas en `requirements.txt` (FastAPI, Pydantic v2,
uvicorn, httpx y pytest). SQLite viene en la biblioteca estándar.

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

## Ejecución

```sh
.venv/Scripts/python -m uvicorn reservas.main:app --app-dir src
```

La API queda en `http://127.0.0.1:8000`, con documentación interactiva en `/docs`.

La ruta del archivo SQLite sale de la variable de entorno `RESERVAS_DB_PATH`, con
`data/reservas.db` por defecto. El archivo se crea al iniciar, con el esquema y el
inventario cargados.

```sh
# PowerShell
$env:RESERVAS_DB_PATH = "data/otra.db"; .venv/Scripts/python -m uvicorn reservas.main:app --app-dir src
```

## Endpoints

| Método y ruta | Uso |
|---|---|
| `GET /units` | Inventario completo, ordenado por ID |
| `GET /units/{unit_id}/availability?start=&end=` | Disponibilidad de una unidad en un intervalo |
| `POST /reservations` | Crear una reserva |
| `GET /reservations?unit_id=&status=` | Historial, con filtros opcionales |
| `GET /reservations/{id}` | Una reserva |
| `POST /reservations/{id}/cancel` | Cancelar conservando el registro |

Las fechas de entrada son ISO 8601 con offset obligatorio; las respuestas vienen en UTC
con sufijo `Z`. En una query string, el `+` de un offset se escribe `%2B`, o se usa `Z`.

```sh
curl http://127.0.0.1:8000/units

curl "http://127.0.0.1:8000/units/MIC-01/availability?start=2026-11-03T10:00:00-03:00&end=2026-11-03T11:00:00-03:00"

curl -X POST http://127.0.0.1:8000/reservations \
  -H "Content-Type: application/json" \
  -d '{"unit_id":"MIC-01","requester":"Ana Pérez","start":"2026-11-03T10:00:00-03:00","end":"2026-11-03T11:00:00-03:00"}'

curl -X POST http://127.0.0.1:8000/reservations/1/cancel
```

Toda respuesta 4xx usa el mismo sobre, con un código estable:

```json
{ "error": { "code": "OVERLAP", "message": "...", "details": [] } }
```

Los códigos posibles están en la sección 7.4 de la spec.

## Pruebas

```sh
.venv/Scripts/python -m pytest
```

Las pruebas derivan de los criterios de aceptación CA-01 a CA-34 de la spec. No hace
falta instalar el paquete: `pyproject.toml` fija `pythonpath = ["src"]`.

## Reinicio de datos

Borra el archivo de la base y con él **todas** las reservas, activas y canceladas. Es
irreversible y pide confirmación: hay que escribir la palabra `BORRAR`.

```sh
.venv/Scripts/python src/reservas/reset_data.py
.venv/Scripts/python src/reservas/reset_data.py --db-path data/otra.db
.venv/Scripts/python src/reservas/reset_data.py --yes   # sin preguntar, uso no interactivo
```

Sin `--db-path`, usa la misma ruta que el servidor: `RESERVAS_DB_PATH` o
`data/reservas.db`. Códigos de salida: `0` si borró o no había nada que borrar, `1` si se
canceló la confirmación, `2` si la ruta no es un archivo.

Detené el servidor antes de reiniciar los datos: si sigue corriendo, va a volver a crear
el archivo vacío en el próximo pedido.

## Verificación manual de la persistencia (CA-29 y CA-30)

Reproduce con el servidor real lo que las pruebas verifican con dos aplicaciones sobre el
mismo archivo. Usá fechas futuras: no se puede reservar en el pasado (S-03).

1. Iniciar el servidor:
   `.venv/Scripts/python -m uvicorn reservas.main:app --app-dir src`
2. Crear dos reservas de MIC-01 en días distintos, con los `curl` de arriba. Anotar los
   dos ID.
3. Cancelar la segunda: `curl -X POST http://127.0.0.1:8000/reservations/2/cancel`
4. Listar y guardar el resultado: `curl http://127.0.0.1:8000/reservations`
5. Detener el proceso con Ctrl+C.
6. Volver a iniciarlo con el mismo comando.
7. Listar de nuevo: aparecen las dos reservas, con los mismos ID, datos y estados.
8. Crear otra vez la primera reserva: responde `409 OVERLAP`, porque sigue activa.
9. Crear otra vez la segunda: responde `201`, porque estaba cancelada y no ocupa su
   intervalo.

## Estructura

| Ruta | Contenido |
|---|---|
| `src/reservas/models.py` | Modelos del contrato (sección 7.2) |
| `src/reservas/domain.py` | Reglas de negocio y validaciones (secciones 4 y 5) |
| `src/reservas/storage.py` | Persistencia SQLite (sección 8) |
| `src/reservas/errors.py` | Códigos de error y sobre único de las 4xx (sección 7.4) |
| `src/reservas/api.py` | `create_app(*, db_path, clock)` y los seis endpoints (sección 7.3) |
| `src/reservas/config.py` | Ruta de la base y reloj del sistema |
| `src/reservas/main.py` | Aplicación para uvicorn |
| `src/reservas/reset_data.py` | Comando de reinicio de datos |
| `src/reservas/inventory.json` | Inventario precargado (sección 3) |
| `tests/` | Pruebas derivadas de la spec |
| `docs/` | Especificación y registro de decisiones |

La regla de superposición vive en una sola función, `domain.intervals_overlap`, que usan
tanto la creación de reservas como la consulta de disponibilidad. Es lo que garantiza
R-07: si la consulta dice disponible, la creación con los mismos datos no falla por
superposición.
