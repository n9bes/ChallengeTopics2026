# Especificación: sistema de reservas del laboratorio

| | |
|---|---|
| Versión | 1.0.0 |
| Fecha | 2026-10-24 |
| Estado del contrato | **CONGELADO**, aprobado por el humano el 2026-10-24 |

Los subagentes de implementación y pruebas no empiezan hasta que el estado del contrato diga
`CONGELADO`. Cambiar el contrato después de congelado exige subir la versión y registrar el
motivo en `docs/decisions.md`.

---

## 1. Problema

La coordinación de un laboratorio registra pedidos de equipos en mensajes y en una planilla.
Esto produce dos fallas: se confirma la misma unidad para horarios superpuestos, y una
cancelación sigue bloqueando el horario. Se necesita consultar disponibilidad, reservar y
cancelar sin perder el historial.

## 2. Alcance

**Dentro:**

- Leer el inventario precargado.
- Consultar disponibilidad de una unidad en un intervalo.
- Crear una reserva de una unidad.
- Cancelar una reserva conservando su registro.
- Listar y consultar reservas, activas y canceladas.
- Persistir reservas y estados entre reinicios.

**Fuera**, según la consigna: administración del inventario, autenticación y roles,
notificaciones, pagos, integraciones externas, despliegue, interfaz gráfica, concurrencia
distribuida y escalabilidad de producción. La interfaz es una API HTTP local.

## 3. Inventario

Fijo, precargado desde `src/reservas/inventory.json`. Cada ID es una unidad física distinta.

| ID | Equipo |
|---|---|
| MIC-01 | Microscopio digital |
| MIC-02 | Microscopio digital |
| OSC-01 | Osciloscopio |
| MUL-01 | Multímetro |
| FUE-01 | Fuente de alimentación |

## 4. Reglas de negocio

| ID | Regla |
|---|---|
| R-01 | Una reserva tiene una sola unidad, un solicitante, un inicio y un fin. |
| R-02 | Los intervalos son semiabiertos: `[inicio, fin)`. El instante `fin` no pertenece a la reserva. |
| R-03 | Dos intervalos de la misma unidad se superponen si y solo si `a.inicio < b.fin` y `b.inicio < a.fin`. |
| R-04 | Solo las reservas **activas** ocupan su intervalo. Una cancelada no bloquea nada. |
| R-05 | Se rechaza crear una reserva que se superpone con una activa de la misma unidad. |
| R-06 | Reservas de unidades distintas nunca entran en conflicto entre sí. |
| R-07 | La consulta de disponibilidad aplica R-03 y R-04 con la misma lógica que la creación. Si la consulta dice disponible, la creación con los mismos datos no falla por superposición. |
| R-08 | Cancelar cambia el estado a `cancelled` y registra el momento. Conserva identificador y datos. Nunca se borra una reserva. |
| R-09 | Solo se cancela una reserva activa. |

Consecuencia directa de R-02 y R-03, que es el ejemplo de la consigna: con MIC-01 reservado
de 10:00 a 11:00, se rechaza 10:30 a 11:30, se acepta 11:00 a 12:00, y MIC-02 se puede
reservar de 10:00 a 11:00.

## 5. Validaciones

| ID | Validación | Rechazo |
|---|---|---|
| V-01 | La unidad existe en el inventario. Comparación exacta, sensible a mayúsculas. | `UNKNOWN_UNIT` |
| V-02 | El solicitante, sin espacios al inicio ni al final, tiene entre 1 y 100 caracteres. | `INVALID_REQUESTER` |
| V-03 | Inicio y fin son fechas y horas válidas en ISO 8601 **con offset**. | `VALIDATION_ERROR` |
| V-04 | El inicio es estrictamente anterior al fin. | `INVALID_INTERVAL` |
| V-05 | Al crear, el inicio no es anterior al momento actual. | `START_IN_PAST` |
| V-06 | Al crear, el inicio es como máximo 30 días posterior al momento actual. | `TOO_FAR_AHEAD` |
| V-07 | La duración, fin menos inicio, es como máximo 30 días. | `DURATION_TOO_LONG` |

En V-06 y V-07, 30 días es un intervalo fijo de 30 × 24 horas, y el límite exacto se acepta.

## 6. Supuestos

Decisiones sobre lo que la consigna no especifica. Cada una es coherente con las demás y se
registra con su motivo en `docs/decisions.md`.

| ID | Supuesto | Motivo |
|---|---|---|
| S-01 | Fechas en ISO 8601 / RFC 3339 con offset obligatorio, por ejemplo `2026-11-03T10:00:00-03:00` o `2026-11-03T13:00:00Z`. Una hora sin offset se rechaza. | Elimina la ambigüedad de zona horaria sin configuración implícita. Elegido por el humano. |
| S-02 | Internamente todo se normaliza a UTC. Las respuestas devuelven UTC con sufijo `Z`. | Comparaciones correctas entre offsets distintos. 10:00-03:00 y 13:00Z son el mismo instante. |
| S-03 | No se puede crear una reserva con inicio en el pasado. Un inicio igual al momento actual se acepta. La consulta de disponibilidad acepta cualquier rango. | Evita reservas sin sentido operativo. Elegido por el humano. |
| S-04 | Duración y anticipación máximas de 30 días (V-06, V-07). Un mes se mide como 30 días fijos, no como mes calendario. Los límites aplican al crear, no a la consulta de disponibilidad. | Evitar que una reserva larga o muy anticipada deje una unidad compartida inaccesible para el resto del laboratorio. 30 días fijos es determinista y no depende de la longitud de cada mes. Elegido por el humano, ver D-007. |
| S-05 | Se admite precisión de segundos y fracciones. No se redondea. | Redondear cambiaría datos del usuario sin avisar. |
| S-06 | El solicitante se guarda sin los espacios iniciales y finales. Límite de 100 caracteres. | V-02 se valida sobre el valor recortado; el límite es una cota defensiva de entrada. |
| S-07 | Se puede cancelar una reserva activa aunque su horario ya haya pasado. | Cancelar no crea ocupación; no hay riesgo que prevenir. |
| S-08 | El momento actual sale de un reloj inyectable. | Las pruebas de S-03 deben ser deterministas. |
| S-09 | Un solo proceso local. La verificación de superposición y la inserción ocurren en la misma transacción de escritura. | Correcto ante pedidos simultáneos al mismo servidor, sin pretender concurrencia distribuida. |
| S-10 | En una query string, el `+` de un offset debe codificarse como `%2B`, o usarse `Z`. | Es comportamiento estándar de URLs: un `+` sin codificar llega como espacio. |

---

## 7. Contrato de la API

Base: `http://127.0.0.1:8000`. Cuerpos en JSON, UTF-8.

### 7.1 Punto de entrada en Python

```python
# módulo reservas.api
def create_app(*, db_path: Path, clock: Callable[[], datetime]) -> FastAPI: ...
```

- `db_path`: archivo SQLite. Se crea si no existe, con el esquema y el inventario cargados.
- `clock`: devuelve el momento actual como `datetime` con zona horaria.
- Crear dos aplicaciones sobre el mismo `db_path` equivale a reiniciar el servidor. Así se
  prueba la persistencia.

Para ejecución normal, la aplicación lee la ruta de la variable `RESERVAS_DB_PATH`, con
`data/reservas.db` como valor por defecto, y usa el reloj del sistema en UTC.

### 7.2 Modelos

**Unit**

```json
{ "id": "MIC-01", "name": "Microscopio digital" }
```

**ReservationCreate**, cuerpo de entrada

```json
{
  "unit_id": "MIC-01",
  "requester": "Ana Pérez",
  "start": "2026-11-03T10:00:00-03:00",
  "end": "2026-11-03T11:00:00-03:00"
}
```

Los cuatro campos son obligatorios. Campos extra se ignoran.

**Reservation**, respuesta

```json
{
  "id": 1,
  "unit_id": "MIC-01",
  "requester": "Ana Pérez",
  "start": "2026-11-03T13:00:00Z",
  "end": "2026-11-03T14:00:00Z",
  "status": "active",
  "created_at": "2026-11-02T12:00:00Z",
  "cancelled_at": null
}
```

- `id`: entero, asignado por el sistema, nunca se reutiliza.
- `status`: `"active"` o `"cancelled"`.
- `cancelled_at`: `null` mientras esté activa.

**Availability**, respuesta

```json
{
  "unit_id": "MIC-01",
  "start": "2026-11-03T13:30:00Z",
  "end": "2026-11-03T14:30:00Z",
  "available": false,
  "conflicts": [ { "...": "Reservation" } ]
}
```

`conflicts` lista las reservas activas que se superponen, ordenadas por inicio. Vacía si
`available` es `true`.

**Error**, toda respuesta 4xx

```json
{
  "error": {
    "code": "OVERLAP",
    "message": "La unidad MIC-01 ya tiene una reserva activa en ese intervalo.",
    "details": [ { "reservation_id": 1, "start": "2026-11-03T13:00:00Z", "end": "2026-11-03T14:00:00Z" } ]
  }
}
```

- `code`: estable, para que lo verifiquen las pruebas. Ver 7.4.
- `message`: texto en español para personas. No es parte estable del contrato.
- `details`: lista, puede estar vacía. En `VALIDATION_ERROR` contiene `loc`, `msg` y `type`
  de cada campo inválido.

### 7.3 Endpoints

| Método y ruta | Uso | Éxito | Errores |
|---|---|---|---|
| `GET /units` | Inventario completo, ordenado por ID | `200`, lista de Unit | |
| `GET /units/{unit_id}/availability?start=&end=` | Disponibilidad de una unidad en un intervalo | `200`, Availability | `404 UNIT_NOT_FOUND`, `422 VALIDATION_ERROR`, `422 INVALID_INTERVAL` |
| `POST /reservations` | Crear reserva | `201`, Reservation | `409 OVERLAP`, `422 UNKNOWN_UNIT`, `422 INVALID_REQUESTER`, `422 INVALID_INTERVAL`, `422 START_IN_PAST`, `422 TOO_FAR_AHEAD`, `422 DURATION_TOO_LONG`, `422 VALIDATION_ERROR` |
| `GET /reservations?unit_id=&status=` | Historial, filtros opcionales, ordenado por inicio y luego por ID | `200`, lista de Reservation | `422 UNKNOWN_UNIT`, `422 VALIDATION_ERROR` |
| `GET /reservations/{id}` | Una reserva | `200`, Reservation | `404 RESERVATION_NOT_FOUND` |
| `POST /reservations/{id}/cancel` | Cancelar | `200`, Reservation cancelada | `404 RESERVATION_NOT_FOUND`, `409 ALREADY_CANCELLED` |

Cancelar usa `POST` sobre una acción y no `DELETE`: la reserva no se elimina (R-08), y
`DELETE` comunicaría lo contrario.

### 7.4 Códigos de error

| Código | HTTP | Cuándo |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Falta un campo, tipo incorrecto, fecha inexistente, hora sin offset, `status` de filtro inválido. |
| `UNKNOWN_UNIT` | 422 | La unidad del cuerpo o del filtro no existe (V-01). |
| `INVALID_REQUESTER` | 422 | Solicitante vacío, solo espacios o más de 100 caracteres (V-02). |
| `INVALID_INTERVAL` | 422 | Inicio igual o posterior al fin (V-04). |
| `START_IN_PAST` | 422 | Inicio anterior al momento actual al crear (V-05). |
| `TOO_FAR_AHEAD` | 422 | Inicio más de 30 días posterior al momento actual al crear (V-06). |
| `DURATION_TOO_LONG` | 422 | Duración mayor a 30 días (V-07). |
| `OVERLAP` | 409 | Superposición con una reserva activa de la misma unidad (R-05). `details` lista las reservas en conflicto. |
| `ALREADY_CANCELLED` | 409 | La reserva ya estaba cancelada (R-09). |
| `UNIT_NOT_FOUND` | 404 | La unidad de la ruta no existe. |
| `RESERVATION_NOT_FOUND` | 404 | El ID de reserva no existe. |

Orden de evaluación al crear, para que el código devuelto sea predecible cuando hay varios
problemas: `VALIDATION_ERROR`, `UNKNOWN_UNIT`, `INVALID_REQUESTER`, `INVALID_INTERVAL`,
`START_IN_PAST`, `TOO_FAR_AHEAD`, `DURATION_TOO_LONG`, `OVERLAP`.

---

## 8. Persistencia

SQLite, un archivo. Ruta según 7.1. El esquema es orientativo para el implementador; lo
contractual es el comportamiento observable.

- Tabla `units`: cargada desde `inventory.json` al iniciar, sin duplicar si ya existe.
- Tabla `reservations`: una fila por reserva, nunca se borra. Fechas en UTC como texto de
  formato fijo `YYYY-MM-DDTHH:MM:SS.ffffffZ`, que ordena igual en texto que en tiempo y es
  legible al inspeccionar la base a mano.
- Restricciones en la base, como respaldo de las validaciones: clave foránea a `units`,
  `status` en `('active', 'cancelled')`, inicio menor que fin.

El reinicio de datos borra el archivo y con él **todas las reservas**, activas y canceladas.
Se hace con un comando explícito documentado en el README, que pide confirmación.

## 9. Estructura

Directorios asignados a cada agente:

| Directorio | Contenido | Escribe |
|---|---|---|
| `src/reservas/` | Dominio, persistencia, API, inventario | `domain-builder` |
| `tests/` | Pruebas automáticas | `contract-tester` |
| `docs/` | Especificación, decisiones, preparación del agente | sesión principal |
| `data/` | Base SQLite en ejecución normal, fuera de git | la aplicación |

Herramientas: Python 3.11 o superior, FastAPI, Pydantic v2, SQLite de la biblioteca
estándar, pytest, httpx para el `TestClient` de FastAPI. Las versiones exactas quedan
fijadas en el archivo de bloqueo al armar el proyecto.

---

## 10. Criterios de aceptación

Reloj de referencia para todos los casos: `2026-11-02T12:00:00Z`. Las horas se escriben en
`-03:00` salvo que se indique otra cosa. "Base" significa una reserva previa activa de
MIC-01 de 10:00 a 11:00 del 2026-11-03.

Cada criterio tiene al menos una prueba cuyo nombre empieza con su ID, por ejemplo
`test_ca02_rechaza_superposicion_parcial`.

| ID | Requisito de la consigna | Dado | Cuando | Entonces |
|---|---|---|---|---|
| CA-01 | Inventario precargado | Base vacía | `GET /units` | `200`, exactamente las 5 unidades de la sección 3 |
| CA-02 | Creación válida | Base vacía | Crear MIC-01 10:00 a 11:00 | `201`, `status` `active`, `id` asignado, horas en UTC: 13:00Z a 14:00Z |
| CA-03 | Rechazo de superposición | Base | Crear MIC-01 10:30 a 11:30 | `409 OVERLAP`, `details` contiene el ID de la base |
| CA-04 | Rechazo de superposición | Base | Crear MIC-01 10:15 a 10:45, contenida | `409 OVERLAP` |
| CA-05 | Rechazo de superposición | Base | Crear MIC-01 09:00 a 12:00, envolvente | `409 OVERLAP` |
| CA-06 | Rechazo de superposición | Base | Crear MIC-01 10:00 a 11:00, idéntica | `409 OVERLAP` |
| CA-07 | Límites consecutivos | Base | Crear MIC-01 11:00 a 12:00 | `201` |
| CA-08 | Límites consecutivos | Base | Crear MIC-01 09:00 a 10:00 | `201` |
| CA-09 | Unidades distintas simultáneas | Base | Crear MIC-02 10:00 a 11:00 | `201` |
| CA-10 | Superposición entre offsets | Base | Crear MIC-01 13:30Z a 14:30Z | `409 OVERLAP` |
| CA-11 | Entrada inválida | Base vacía | Crear con unidad `XYZ-99` | `422 UNKNOWN_UNIT` |
| CA-12 | Entrada inválida | Base vacía | Crear con unidad `mic-01` | `422 UNKNOWN_UNIT` |
| CA-13 | Entrada inválida | Base vacía | Crear con solicitante `""` | `422 INVALID_REQUESTER` |
| CA-14 | Entrada inválida | Base vacía | Crear con solicitante `"   "` | `422 INVALID_REQUESTER` |
| CA-15 | Entrada inválida | Base vacía | Crear con `"start": "2026-11-03T10:00:00"`, sin offset | `422 VALIDATION_ERROR` |
| CA-16 | Entrada inválida | Base vacía | Crear con fecha `2026-02-30T10:00:00-03:00` | `422 VALIDATION_ERROR` |
| CA-17 | Entrada inválida | Base vacía | Crear con inicio igual al fin | `422 INVALID_INTERVAL` |
| CA-18 | Entrada inválida | Base vacía | Crear con inicio posterior al fin | `422 INVALID_INTERVAL` |
| CA-19 | Fechas pasadas, S-03 | Base vacía | Crear MIC-01 de `2026-11-02T08:00:00-03:00` a `2026-11-02T10:00:00-03:00`: empieza en el pasado y termina en el futuro | `422 START_IN_PAST` |
| CA-20 | Fechas pasadas, S-03 | Base vacía | Crear MIC-01 de `2026-11-02T12:00:00Z`, exactamente el reloj, a `2026-11-02T13:00:00Z` | `201` |
| CA-21 | Cancelación conserva el registro | Base | Cancelar la base y luego `GET` por su ID | `200` en ambos, `status` `cancelled`, `cancelled_at` no nulo, mismo ID, unidad, solicitante y horas |
| CA-22 | Cancelación libera el horario | Base cancelada | Crear MIC-01 10:00 a 11:00 | `201`, con un ID distinto al de la base |
| CA-23 | Cancelación conserva el registro | Base cancelada y una nueva activa en el mismo horario | `GET /reservations?unit_id=MIC-01` | Aparecen las dos, una `cancelled` y otra `active` |
| CA-24 | R-09 | Base cancelada | Cancelar otra vez | `409 ALREADY_CANCELLED` |
| CA-25 | Cancelar inexistente | Base vacía | Cancelar el ID 999 | `404 RESERVATION_NOT_FOUND` |
| CA-26 | Disponibilidad con las mismas reglas | Base | Consultar MIC-01 en los intervalos de CA-03 a CA-08 y MIC-02 10:00 a 11:00 | `available` es `false` donde la creación da `409` y `true` donde da `201`. `conflicts` contiene la base cuando es `false` |
| CA-27 | Disponibilidad tras cancelar | Base cancelada | Consultar MIC-01 10:00 a 11:00 | `available` `true`, `conflicts` vacía |
| CA-28 | Disponibilidad, unidad desconocida | Base vacía | Consultar `XYZ-99` | `404 UNIT_NOT_FOUND` |
| CA-29 | Persistencia tras reinicio | Una reserva activa y otra cancelada, creadas con una aplicación | Crear una aplicación nueva sobre el mismo archivo y listar | Las dos reservas con los mismos ID, datos y estados |
| CA-30 | Persistencia tras reinicio | El estado de CA-29 tras el reinicio | Crear sobre el horario de la activa y sobre el de la cancelada | `409 OVERLAP` en la primera, `201` en la segunda |
| CA-31 | Duración máxima, S-04 | Base vacía | Crear MIC-01 de `2026-11-03T13:00:00Z` a `2026-12-03T13:00:00Z`, 30 días exactos | `201` |
| CA-32 | Duración máxima, S-04 | Base vacía | Crear MIC-01 de `2026-11-03T13:00:00Z` a `2026-12-03T13:00:01Z`, 30 días y 1 segundo | `422 DURATION_TOO_LONG` |
| CA-33 | Anticipación máxima, S-04 | Base vacía | Crear MIC-01 de `2026-12-02T12:00:00Z`, el reloj más 30 días exactos, a `2026-12-02T13:00:00Z` | `201` |
| CA-34 | Anticipación máxima, S-04 | Base vacía | Crear MIC-01 de `2026-12-02T12:00:01Z` a `2026-12-02T13:00:00Z` | `422 TOO_FAR_AHEAD` |

Además, un procedimiento manual reproducible en el README verifica CA-29 y CA-30 con el
servidor real: iniciar, crear, detener el proceso, volver a iniciar y consultar.

---

## Historial de cambios

| Versión | Fecha | Cambio |
|---|---|---|
| 0.1.0 | 2026-10-24 | Versión inicial. Supuestos S-01, S-03 y S-04 elegidos por el humano. Antes del primer commit, S-04 pasó de "sin límites" a máximo 30 días de duración y de anticipación (D-007). |
| 1.0.0 | 2026-10-24 | Contrato congelado tras revisión humana, sin cambios de contenido respecto de 0.1.0. Habilita a `domain-builder` y `contract-tester`. |
