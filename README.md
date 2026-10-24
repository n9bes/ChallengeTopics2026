# Sistema de reservas del laboratorio

API HTTP local para consultar disponibilidad, reservar y cancelar equipos de laboratorio
sin perder el historial. Python 3.11, FastAPI, Pydantic v2 y SQLite de la biblioteca
estándar.

Este README está organizado en las cuatro secciones que pide la consigna y enlaza los
archivos de `docs/`, que son la fuente: [`spec.md`](docs/spec.md) para el contrato,
[`decisions.md`](docs/decisions.md) para las decisiones y los episodios de delegación, y
[`agent-setup.md`](docs/agent-setup.md) para la preparación del agente.

---

## 1. Especificación breve

El contrato completo y versionado está en [`docs/spec.md`](docs/spec.md). Resumen:

**Problema.** La coordinación de un laboratorio registra pedidos de equipos en mensajes y en
una planilla. Eso produce dos fallas concretas: se confirma la misma unidad para horarios
superpuestos, y una cancelación sigue bloqueando el horario.

**Alcance.** Dentro: leer el inventario precargado, consultar disponibilidad de una unidad en
un intervalo, crear una reserva, cancelarla conservando su registro, listar el historial y
persistir todo entre reinicios. Fuera: administración del inventario, autenticación y roles,
notificaciones, pagos, integraciones externas, despliegue, interfaz gráfica, concurrencia
distribuida y escalabilidad de producción.

**Reglas, las que más importan.** Los intervalos son semiabiertos `[inicio, fin)`. Dos
reservas de la misma unidad se superponen si y solo si `a.inicio < b.fin y b.inicio < a.fin`,
con comparación estricta: 10:00 a 11:00 y 11:00 a 12:00 no se superponen. Solo las reservas
activas ocupan su intervalo, así que una cancelada no bloquea nada. Cancelar conserva
identificador y datos; nunca se borra una reserva. La consulta de disponibilidad usa la misma
función de superposición que la creación, de modo que si la consulta dice disponible, la
creación con los mismos datos no falla por superposición.

**Validaciones.** Unidad conocida con comparación sensible a mayúsculas, solicitante no vacío
ni solo espacios y de hasta 100 caracteres, fechas válidas en ISO 8601 con offset, inicio
estrictamente anterior al fin, y al crear: inicio no anterior al momento actual, anticipación
máxima de 30 días y duración máxima de 30 días. Cada rechazo tiene un código estable, y la
spec fija el orden de evaluación para que el código devuelto sea predecible cuando hay varios
problemas a la vez.

**Supuestos.** Los cuatro que más afectan al uso: offset obligatorio en las fechas, una hora
sin offset se rechaza (S-01); todo se normaliza a UTC y las respuestas vuelven con sufijo `Z`
(S-02); no se puede crear una reserva con inicio en el pasado, aunque un inicio igual al
momento actual se acepta (S-03); duración y anticipación máximas de 30 días fijos, con el
límite exacto aceptado (S-04). Los doce supuestos están en la sección 6 de la spec, cada uno
con su motivo.

**Criterios de aceptación.** CA-01 a CA-36 en la sección 10 de la spec, cada uno con al menos
una prueba automática cuyo nombre empieza con su ID.

**Evolución recuperable.** La spec pasó por 0.1.0, 1.0.0 (congelada, que es la que habilitó a
los subagentes a trabajar) y 1.1.0. Cada cambio está en el historial al final de la spec con
su motivo, y en el registro de decisiones: D-007 cambió los límites de duración y
anticipación antes del primer commit, y el episodio 1 documentó dos comportamientos
observables como supuestos S-11 y S-12.

---

## 2. Solución

### Estructura

| Ruta | Contenido |
|---|---|
| `src/reservas/models.py` | Modelos del contrato (sección 7.2 de la spec) |
| `src/reservas/domain.py` | Reglas de negocio y validaciones (secciones 4 y 5) |
| `src/reservas/storage.py` | Persistencia SQLite (sección 8) |
| `src/reservas/errors.py` | Códigos de error y sobre único de las 4xx (sección 7.4) |
| `src/reservas/api.py` | `create_app(*, db_path, clock)` y los seis endpoints (sección 7.3) |
| `src/reservas/config.py` | Ruta de la base y reloj del sistema |
| `src/reservas/main.py` | Aplicación para uvicorn |
| `src/reservas/reset_data.py` | Comando de reinicio de datos |
| `src/reservas/inventory.json` | Inventario precargado (sección 3) |
| `tests/` | Pruebas derivadas de la spec |
| `docs/spec.md` | Contrato: reglas, validaciones, supuestos, API y criterios de aceptación |
| `docs/decisions.md` | Decisiones con su motivo, y los tres episodios de delegación |
| `docs/agent-setup.md` | Preparación del agente: entorno, instrucciones, permisos, adaptación |

### Decisiones técnicas

Las que tienen consecuencias visibles, con su motivo completo en
[`docs/decisions.md`](docs/decisions.md):

- **La regla de superposición vive en una sola función**, `domain.intervals_overlap`, que
  usan tanto la creación de reservas como la consulta de disponibilidad. No hay una versión
  en SQL. Es lo que garantiza R-07, y el precio es traer de la base las reservas activas de
  la unidad en lugar de filtrarlas en la consulta.
- **El punto de entrada es una fábrica**, `create_app(*, db_path, clock)`, con la base y el
  reloj inyectados. Crear dos aplicaciones sobre el mismo archivo equivale a reiniciar el
  servidor, y así se prueba la persistencia sin levantar procesos. El reloj inyectable hace
  deterministas las pruebas de fechas pasadas (D-006, S-08).
- **Cancelar es `POST /reservations/{id}/cancel`, no `DELETE`**, porque la reserva no se
  elimina y `DELETE` comunicaría lo contrario (D-006).
- **Toda respuesta 4xx usa el mismo sobre** con un código estable, incluidos los errores de
  validación de FastAPI, normalizados con un manejador de `RequestValidationError`. Sin eso,
  dos rechazos distintos con el mismo status 422 serían indistinguibles para una prueba.
- **La verificación de superposición y la inserción ocurren en la misma transacción**, con
  `BEGIN IMMEDIATE` (S-09).
- **Dependencias con pip y `requirements.txt` como archivo de bloqueo**, sin instalar el
  paquete: pytest lo encuentra con `pythonpath = ["src"]` y uvicorn con `--app-dir src`
  (D-008).

### Requisitos previos y versiones

Python 3.11 o superior. Las versiones exactas, incluidas las transitivas, están fijadas en
`requirements.txt`, generado con `pip freeze` en Python 3.11.9 sobre Windows;
`requirements.in` lista las cuatro dependencias directas. SQLite viene en la biblioteca
estándar. No hace falta cuenta de modelo ni ninguna herramienta de IA para instalar, correr
ni probar la aplicación.

Versiones principales del bloqueo: fastapi 0.162.0, pydantic 2.14.1, uvicorn 0.54.0,
httpx 0.28.1, pytest 9.1.1.

### Instalación y carga inicial

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

No hay paso de carga inicial manual: el archivo SQLite se crea al iniciar la aplicación, con
el esquema y las cinco unidades de `inventory.json` ya cargadas. Si el archivo existe, el
inventario no se duplica.

### Comandos de aplicación y pruebas

```sh
.venv/Scripts/python -m uvicorn reservas.main:app --app-dir src
```

La API queda en `http://127.0.0.1:8000`, con documentación interactiva en `/docs`.

```sh
.venv/Scripts/python -m pytest
```

Son 80 pruebas, derivadas de los criterios de aceptación CA-01 a CA-36. No hace falta
instalar el paquete: `pyproject.toml` fija `pythonpath = ["src"]`.

### Endpoints

| Método y ruta | Uso |
|---|---|
| `GET /units` | Inventario completo, ordenado por ID |
| `GET /units/{unit_id}/availability?start=&end=` | Disponibilidad de una unidad en un intervalo |
| `POST /reservations` | Crear una reserva |
| `GET /reservations?unit_id=&status=` | Historial, con filtros opcionales |
| `GET /reservations/{id}` | Una reserva |
| `POST /reservations/{id}/cancel` | Cancelar conservando el registro |

Las fechas de entrada son ISO 8601 con offset obligatorio; las respuestas vienen en UTC con
sufijo `Z`. En una query string, el `+` de un offset se escribe `%2B`, o se usa `Z`.

### Ejemplo de entrada y salida

Las salidas de abajo son reales, capturadas de la aplicación corriendo con el reloj del
sistema.

Crear una reserva:

```sh
curl -X POST http://127.0.0.1:8000/reservations \
  -H "Content-Type: application/json" \
  -d '{"unit_id":"MIC-01","requester":"Ana Pérez","start":"2026-11-03T10:00:00-03:00","end":"2026-11-03T11:00:00-03:00"}'
```

`201`, con las horas normalizadas a UTC:

```json
{
  "id": 1,
  "unit_id": "MIC-01",
  "requester": "Ana Pérez",
  "start": "2026-11-03T13:00:00Z",
  "end": "2026-11-03T14:00:00Z",
  "status": "active",
  "created_at": "2026-10-24T23:53:34.694790Z",
  "cancelled_at": null
}
```

El mismo pedido una segunda vez. `409`, con el sobre de error que usan todas las 4xx y un
`details` que señala la reserva en conflicto:

```json
{
  "error": {
    "code": "OVERLAP",
    "message": "La unidad MIC-01 ya tiene una reserva activa en ese intervalo.",
    "details": [
      { "reservation_id": 1, "start": "2026-11-03T13:00:00Z", "end": "2026-11-03T14:00:00Z" }
    ]
  }
}
```

Consultar disponibilidad del mismo intervalo:

```sh
curl "http://127.0.0.1:8000/units/MIC-01/availability?start=2026-11-03T10:00:00-03:00&end=2026-11-03T11:00:00-03:00"
```

`200`, con la respuesta coherente con el rechazo de arriba, que es el requisito R-07:

```json
{
  "unit_id": "MIC-01",
  "start": "2026-11-03T13:00:00Z",
  "end": "2026-11-03T14:00:00Z",
  "available": false,
  "conflicts": [ { "id": 1, "unit_id": "MIC-01", "requester": "Ana Pérez", "...": "Reservation completa" } ]
}
```

Cancelar:

```sh
curl -X POST http://127.0.0.1:8000/reservations/1/cancel
```

`200`. Conserva ID, unidad, solicitante y horas, y agrega el momento de la cancelación:

```json
{
  "id": 1,
  "unit_id": "MIC-01",
  "requester": "Ana Pérez",
  "start": "2026-11-03T13:00:00Z",
  "end": "2026-11-03T14:00:00Z",
  "status": "cancelled",
  "created_at": "2026-10-24T23:53:34.694790Z",
  "cancelled_at": "2026-10-24T23:53:34.711211Z"
}
```

Después de eso, consultar el mismo intervalo devuelve `available: true` con `conflicts`
vacía, y crear la reserva otra vez devuelve `201` con un ID nuevo. La cancelada sigue en
`GET /reservations`.

Los códigos de error posibles están en la sección 7.4 de la spec.

### Dónde persisten los datos

En un archivo SQLite. La ruta sale de la variable de entorno `RESERVAS_DB_PATH`, con
`data/reservas.db` por defecto. `data/` está fuera de git.

```sh
# PowerShell
$env:RESERVAS_DB_PATH = "data/otra.db"; .venv/Scripts/python -m uvicorn reservas.main:app --app-dir src
```

Las reservas nunca se borran: cancelar solo cambia el estado y registra el momento. No hay
ningún `DELETE` ni `DROP` en el código.

### Reinicio de datos

**Borra el archivo de la base y con él todas las reservas, activas y canceladas.** Es
irreversible y pide confirmación: hay que escribir la palabra `BORRAR`.

```sh
.venv/Scripts/python src/reservas/reset_data.py
.venv/Scripts/python src/reservas/reset_data.py --db-path data/otra.db
.venv/Scripts/python src/reservas/reset_data.py --yes   # sin preguntar, uso no interactivo
```

Sin `--db-path`, usa la misma ruta que el servidor: `RESERVAS_DB_PATH` o `data/reservas.db`.
Códigos de salida: `0` si borró o no había nada que borrar, `1` si se canceló la
confirmación, `2` si la ruta no es un archivo.

Detené el servidor antes de reiniciar los datos: si sigue corriendo, va a volver a crear el
archivo vacío en el próximo pedido.

### Verificación manual de la persistencia (CA-29 y CA-30)

Reproduce con el servidor real lo que las pruebas automáticas verifican con dos aplicaciones
sobre el mismo archivo. Usá fechas futuras: no se puede reservar en el pasado (S-03).

1. Iniciar el servidor:
   `.venv/Scripts/python -m uvicorn reservas.main:app --app-dir src`
2. Crear dos reservas de MIC-01 en días distintos, con los `curl` de arriba. Anotar los dos
   ID.
3. Cancelar la segunda: `curl -X POST http://127.0.0.1:8000/reservations/2/cancel`
4. Listar y guardar el resultado: `curl http://127.0.0.1:8000/reservations`
5. Detener el proceso con Ctrl+C.
6. Volver a iniciarlo con el mismo comando.
7. Listar de nuevo. Esperado: aparecen las dos reservas, con los mismos ID, datos y estados.
8. Crear otra vez la primera reserva. Esperado: `409 OVERLAP`, porque sigue activa.
9. Crear otra vez la segunda. Esperado: `201`, porque estaba cancelada y no ocupa su
   intervalo.

Quién ejecutó qué: ver "Pendientes y limitaciones" abajo.

### Pendientes y limitaciones

- **`/code-review` todavía no corrió.** Es el último paso del flujo descrito en
  `agent-setup.md`.
- **El procedimiento manual de arriba lo ejecutó el subagente `domain-builder`**, que reportó
  haberlo corrido con dos procesos uvicorn y obtener los resultados esperados. La sesión
  principal no lo ejecutó. Lo que la sesión principal sí ejecutó es la verificación
  automática equivalente, CA-29 y CA-30 con dos `create_app` sobre el mismo archivo, que
  pasa. La distinción está sostenida en el episodio 1 de `docs/decisions.md`.
- **La suite emite un warning ajeno al proyecto**,
  `StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated`,
  desde `fastapi/testclient.py` con starlette 1.10.0. Resolverlo exigiría agregar `httpx2`,
  dependencia que el contrato no lista, así que se dejó documentado en lugar de instalado.
- **Sin prueba automática, con motivo:** el comando de reinicio de datos, porque es un CLI
  interactivo cuya prueba implicaría ejercer rutas de borrado; y la lectura de
  `RESERVAS_DB_PATH` con el reloj del sistema, porque verificarla tocaría la base real del
  proyecto. Las pruebas usan siempre una base temporal.
- **S-09 no es observable desde la API** en un solo proceso sin pruebas de concurrencia, que
  están fuera de alcance. Lo que se puede verificar es el código: la verificación y la
  inserción ocurren dentro de la misma transacción.
- **Sin interfaz gráfica.** Diferida por D-004: la consigna no la exige y deja fuera de
  alcance un frente complejo.
- **Un reloj inyectado que devuelva un `datetime` sin zona horaria levanta error 500**, no
  4xx. Es un error de configuración del servidor, no de la solicitud.

---

## 3. Preparación del agente

Todo en [`docs/agent-setup.md`](docs/agent-setup.md): entorno y modelo con el comando que
obtuvo cada versión, las instrucciones realmente usadas y cómo se aplicaron, el contexto
suministrado, qué se excluyó y por qué, las herramientas y acciones permitidas, los cuatro
controles aplicados con el evento real que disparó cada uno, los subagentes del proyecto, la
adaptación específica y la retención del progreso.

La configuración del agente está versionada y es inspeccionable de forma directa:
[`CLAUDE.md`](CLAUDE.md) en la raíz y [`.claude/agents/`](.claude/agents/) con las tres
definiciones de subagente. Lo único que no se versiona es `.claude/settings.local.json`, con
rutas y permisos de la máquina. [`.claude/settings.json`](.claude/settings.json), que sí se
versiona, declara `git commit` y `git push` como reglas `ask`: ningún commit del repositorio
ocurrió sin aprobación humana explícita.

La adaptación específica es la regla de límites consecutivos. La sección correspondiente de
`agent-setup.md` tiene la cadena completa, eslabón por eslabón: la instrucción en las dos
definiciones de subagente, la regla en la spec, los criterios CA-03 y CA-07, las pruebas que
los cubren, la función que implementa la regla y el commit.

---

## 4. Registro de decisiones y delegación

[`docs/decisions.md`](docs/decisions.md) tiene las decisiones significativas con su motivo,
la alternativa considerada cuando hubo disyuntiva, y la consecuencia: D-001 a D-008, desde el
origen de las instrucciones del proyecto hasta la forma del contrato de la API y el manejo de
dependencias.

Al final del mismo archivo están los tres episodios de delegación, cada uno con objetivo y
requisito, contexto suministrado, extracto de instrucción, resultado del agente, decisión
humana con su motivo y una tabla de evidencia verificable:

- **Episodio 1.** Implementación y pruebas de la fase 1, delegadas en paralelo a
  `domain-builder` y `contract-tester` sobre directorios disjuntos. Incluye el defecto que la
  separación entre implementador y autor de pruebas permitió acotar a una causa única, y la
  decisión humana sobre dos comportamientos que la spec no fijaba.
- **Episodio 2.** Pruebas de los dos criterios que agregó la spec 1.1.0, delegadas a
  `contract-tester` en un segundo pedido.
- **Episodio 3.** El clasificador de permisos del harness bloqueando la instalación de un
  `CLAUDE.md` traído de un repositorio público, y la corrección del procedimiento.

En todo el repositorio se usan solicitantes ficticios. No hay secretos, tokens, credenciales
ni transcripciones completas de conversación.
