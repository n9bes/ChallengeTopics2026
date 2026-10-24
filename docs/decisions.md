# Registro de decisiones

Decisiones significativas, su motivo, la alternativa considerada cuando hubo disyuntiva y
la consecuencia. Se agrega una entrada cuando la decisión se toma, no al final del trabajo.

Formato de fecha: ISO 8601, zona horaria local del autor.

---

## D-001. Instrucciones de proyecto tomadas de un repositorio público

**Fecha:** 2026-10-19

**Decisión.** Usar como `CLAUDE.md` del proyecto el archivo de
`drona23/claude-token-efficient`, 352 bytes, seis reglas de estilo y verificación.

**Motivo.** Reduce verbosidad del agente y, sobre todo, incluye una regla que prohíbe
afirmar versiones, flags o nombres de paquetes sin verificarlos. Esa regla es directamente
útil para una entrega donde la consigna exige no inventar datos.

**Alternativa.** Escribir las instrucciones desde cero. Se descartó porque el archivo ya
cubría lo necesario y la consigna no puntúa la autoría de la configuración.

**Control aplicado.** El clasificador de permisos del harness rechazó descargar el archivo
directamente a disco (`curl -o`), con motivo `Instruction Poisoning`. Se revisó el contenido
completo antes de escribirlo, de forma manual y explícita.

**Consecuencia.** El agente verifica versiones por comando en lugar de declararlas de
memoria. Visible en la tabla de entorno de `agent-setup.md`.

---

## D-002. `.gitignore` selectivo en lugar de exclusión general de la configuración del agente

**Fecha:** 2026-10-19

**Decisión.** Versionar `CLAUDE.md` y `.claude/agents/`. Ignorar únicamente
`.claude/settings.local.json`.

**Motivo.** La consigna asigna 25% a "instrucciones, contexto, permisos y adaptación
específica con evidencia de uso real". La configuración del agente es, en esta entrega,
un entregable.

**Alternativa.** Excluir `CLAUDE.md` y `.claude/` por completo e incluir solo extractos
saneados en la documentación, opción prevista por la consigna. Fue la decisión inicial y se
revirtió.

**Motivo de la reversión.** Al verificar qué ocultaba la regla, el único archivo afectado
era el `CLAUDE.md` público de 352 bytes, sin ningún dato del autor. La configuración
personal vive en `~/.claude/`, fuera del repositorio, y nunca estuvo expuesta. La regla
tenía costo en evidencia y beneficio nulo en privacidad. Además iba a ocultar las
definiciones de agentes al momento de crearlas.

**Consecuencia.** Un evaluador inspecciona la configuración real en lugar de una copia que
puede divergir. `docs/agent-setup.md` pasa de ser la fuente a ser el índice comentado.

---

## D-003. Tres subagentes en lugar de los cinco propuestos

**Fecha:** 2026-10-24

**Decisión.** Definir `domain-builder`, `contract-tester` y `frontend-builder`. La spec, el
registro de evidencia y la revisión quedan en la sesión principal o en herramientas
integradas.

**Propuesta original.** Cinco agentes: `spec-architect`, `core-builder`, `test-verifier`,
`frontend-builder` y `evidence-scribe`, solo descritos en conversación, sin archivos.

**Motivo.** Se contrastó la propuesta con la documentación oficial de subagentes de Claude
Code y con guías de práctica actuales:

- Los subagentes no tienen `AskUserQuestion`. Un `spec-architect` no podría resolver
  ambigüedades con el humano, que es justamente el trabajo de la spec.
- Un subagente no bifurcado arranca con contexto vacío. Un `evidence-scribe` registraría
  decisiones humanas que no presenció.
- La documentación recomienda agentes enfocados, descripciones que distingan uno de otro,
  herramientas mínimas y un formato de salida definido. Los tres agentes definen qué
  devolver y separan lo verificado de lo asumido.
- Ya existen el agente `Plan` y la skill `/code-review`; duplicarlos no agrega control.
- La consigna aclara que la cantidad de agentes no da puntos. La única separación con valor
  técnico es implementador contra autor de pruebas, y se mantiene.

**Alternativa.** Mantener los cinco. Se descartó por las dos limitaciones de herramientas y
contexto de arriba, que harían a dos agentes poco confiables justo en las dimensiones de
especificación y trazabilidad.

**Control agregado.** `.claude/settings.json` con `git commit` y `git push` como reglas
`ask`, para que la regla de no commitear sin aprobación humana la haga cumplir el harness
y no solo una instrucción.

**Consecuencia.** Menos agentes que mantener y cada uno con límites verificables en su
archivo. La UI queda marcada como opcional.

---

## D-004. Interfaz gráfica diferida

**Fecha:** 2026-10-24

**Decisión.** No construir UI por ahora. `frontend-builder` queda definido pero marcado como
diferido en su descripción, para que no se le delegue trabajo.

**Motivo.** La consigna no exige interfaz gráfica, deja fuera de alcance un frente complejo
y aclara que la estética no da puntos. Una API local es suficiente.

**Alternativa.** Borrar el agente. Se descartó porque retomarlo sería rehacer trabajo ya
revisado; marcarlo diferido es reversible con una línea.

---

## D-005. Fechas con offset obligatorio, sin reservas en el pasado, sin límites de duración

**Fecha:** 2026-10-24

**Decisión.** Supuestos S-01, S-03 y S-04 de `docs/spec.md`. Elegidos por el humano entre
alternativas presentadas por el agente.

| Tema | Elegido | Alternativa descartada |
|---|---|---|
| Zona horaria | ISO 8601 con offset obligatorio, normalizado a UTC | Hora local sin offset en una zona configurada |
| Fechas pasadas | Rechazar crear con inicio anterior al momento actual | Permitirlas para cargar historial |
| Límites | Ninguno además de inicio menor que fin. **Reemplazado por D-007.** | Duración máxima de 24 h |

**Motivo.** El offset obligatorio elimina la ambigüedad sin configuración implícita. Rechazar
el pasado evita reservas sin sentido operativo. Un límite de duración sería un requisito que
la consigna no pide.

**Consecuencia.** Pydantic v2 ofrece `AwareDatetime`, que rechaza horas sin zona con el
error `timezone_aware`; se verificó en su documentación. El reloj se inyecta para probar
S-03 de forma determinista.

---

## D-006. Forma del contrato de la API

**Fecha:** 2026-10-24

**Decisión.**

- El punto de entrada es una fábrica `create_app(*, db_path, clock)`.
- Cancelar es `POST /reservations/{id}/cancel`, no `DELETE`.
- Todo error 4xx usa el mismo cuerpo `{"error": {"code", "message", "details"}}`, incluidos
  los errores de validación de FastAPI, normalizados con un manejador de
  `RequestValidationError`.
- IDs de reserva enteros, asignados por SQLite y nunca reutilizados.

**Motivo.**

- La fábrica permite inyectar la base y el reloj. Crear dos aplicaciones sobre el mismo
  archivo prueba la persistencia tras reinicio sin levantar procesos.
- `DELETE` comunicaría que la reserva desaparece, y la regla R-08 dice lo contrario.
- Un código de error estable permite que las pruebas verifiquen el motivo del rechazo y no
  solo el status HTTP. Sin normalizar, FastAPI devuelve `detail` como lista en validación y
  como texto en el resto, y las pruebas tendrían que distinguir formas.

**Alternativa.** Usar las respuestas de error por defecto de FastAPI. Más simple, pero dos
rechazos distintos con el mismo status 422 serían indistinguibles para una prueba.

---

## D-007. Duración y anticipación máximas de 30 días

**Fecha:** 2026-10-24

**Decisión.** Reemplaza la fila "Límites" de D-005. Una reserva dura como máximo 30 días y
empieza como máximo 30 días después del momento actual. Ambos límites exactos se aceptan.
Aplican al crear, no a la consulta de disponibilidad. Nuevos códigos `DURATION_TOO_LONG` y
`TOO_FAR_AHEAD`, criterios CA-31 a CA-34.

**Motivo.** Evitar que una sola reserva larga, o una muy anticipada, deje una unidad
compartida inaccesible para el resto del laboratorio. Decisión del humano al revisar la
spec, antes del primer commit.

**Alternativas.**

| Tema | Elegido | Descartado |
|---|---|---|
| Qué se limita | Duración y anticipación | Solo duración; solo anticipación |
| Cómo se mide un mes | 30 días fijos | Mes calendario |

Limitar solo una de las dos deja abierta la otra forma de bloquear una unidad. El mes
calendario obliga a definir casos como el 31 de enero más un mes; 30 días fijos es
determinista y se prueba sin depender del mes en curso.

**Consecuencia.** Contradice el motivo original de D-005, que veía un límite como requisito
inventado. Se acepta porque ahora hay una razón operativa explícita del humano que lo
respalda, y queda registrada aquí.

---

## D-008. Dependencias con pip y requirements.txt, sin instalar el paquete

**Fecha:** 2026-10-24

**Decisión.** `requirements.in` lista las cuatro dependencias directas. `requirements.txt` es
el archivo de bloqueo: salida de `pip freeze` con versiones exactas, incluidas las
transitivas. El paquete no se instala: pytest lo encuentra con `pythonpath = ["src"]` en
`pyproject.toml`, y uvicorn con `--app-dir src`. Ambas opciones se verificaron en la ayuda
de las versiones instaladas.

**Motivo.** pip viene con Python, así que reproducir el entorno no exige instalar otra
herramienta. Elegido por el humano.

**Alternativa.** uv con `uv.lock`. Se descartó porque uv no estaba instalado y sumaría un
requisito previo. `pip install -e .` se descartó porque exige un backend de build y el
archivo de bloqueo pasaría a incluir una línea editable dependiente de la ruta local.

**Consecuencia.** El bloqueo se generó en Windows e incluye `colorama`, que en otros
sistemas se instala igual aunque no se use. Regenerar exige volver a congelar y conservar
el encabezado del archivo.

---

# Episodios de delegación

Registro de las delegaciones a subagentes. Cada episodio se anota cuando ocurre, con el
resultado tal como lo reportó el agente, separado de lo que verificó la sesión principal
por su cuenta. La decisión final y su motivo los dicta el humano.

---

## Episodio 1. Implementación y pruebas de la fase 1, en paralelo

**Fecha:** 2026-10-24

### Objetivo y requisito

Producir la fase 1 completa a partir del contrato congelado: el código de producción de
`src/reservas/` y la suite de pruebas de `tests/`. El requisito es la sección 10 de
`docs/spec.md`, que traza cada requisito de la consigna a un criterio `CA-01` a `CA-34`,
más los criterios que no vienen de la consigna sino de los supuestos del humano (`CA-31`
a `CA-34`, límites de duración y anticipación de D-007).

La delegación se hizo con dos agentes en paralelo y no con uno solo, para materializar el
Control 3 de `docs/agent-setup.md`: quien implementa no escribe las pruebas que lo
evalúan. Las pruebas se derivan de la spec, de modo que un error del dominio no pueda
quedar justificado por una prueba escrita a su medida.

### Contexto suministrado

| Qué | A quién | Forma |
|---|---|---|
| `docs/spec.md` v1.0.0, contrato CONGELADO | ambos | Leído completo por cada agente |
| `docs/decisions.md`, D-005 a D-008 | `domain-builder` | Referencia al motivo de cada supuesto |
| Definición del propio agente | ambos | `.claude/agents/*.md`, cargada por el harness al iniciar la sesión |
| Directorio asignado y directorios prohibidos | ambos | Explícito en la instrucción: `src/reservas/` contra `tests/` |
| Entorno: `.venv` con Python 3.11.9, ejecutar con `.venv/Scripts/python` | ambos | Explícito en la instrucción |
| Versiones fijadas en `requirements.txt`, sin agregar dependencias | ambos | Explícito en la instrucción |
| `pyproject.toml` con `pythonpath = ["src"]` | ambos | Explícito en la instrucción |

Los dos agentes trabajaron en el mismo turno sobre directorios disjuntos. Ninguno recibió
la transcripción de la sesión principal.

### Extracto de instrucción

A `domain-builder`, sobre el requisito R-07, que es el que más se incumple:

> Una sola función de superposición, compartida por la creación y la consulta de
> disponibilidad. Es el requisito R-07 de la spec: si la consulta dice disponible, la
> creación con los mismos datos no puede fallar por superposición. No dupliques esa
> lógica.
>
> No escribas ni modifiques nada en `tests/`. Otro agente está escribiendo las pruebas en
> paralelo, derivadas solo de la spec.

A `contract-tester`, sobre la independencia del resultado esperado y sobre qué hacer si la
implementación todavía no existe:

> No creés stubs, archivos vacíos, `conftest.py` con dobles, ni ningún sustituto de la
> implementación para que la suite corra. Cuando ejecutes pytest, la implementación puede
> no existir todavía o estar incompleta: reportá el resultado tal cual, incluidos los
> errores de importación. Eso es información válida, no un problema a tapar.
>
> Verificá el status HTTP y `error.code` del cuerpo. Nunca verifiques `error.message`: la
> spec dice en la sección 7.2 que el mensaje no es parte estable del contrato.

Se le indicó además una restricción del entorno que no está en la spec: en `CA-29` y
`CA-30` hay que cerrar el primer `TestClient` antes de construir la segunda aplicación,
porque en Windows SQLite mantiene el archivo bloqueado.

### Resultado de los agentes, según su propio informe

`domain-builder`: 10 módulos en `src/reservas/` más `inventory.json` y un `README.md` en
la raíz, todos nuevos. Reporta que `domain.intervals_overlap` es la única implementación de
R-03 y que la comparación no existe en SQL, que `create_reservation` abre
`BEGIN IMMEDIATE` para verificar e insertar en la misma transacción (S-09), y que no hay
ningún `DELETE` ni `DROP` en el código (R-08). Declara ocho supuestos propios sobre puntos
que la spec no fija, de los cuales dos son observables desde la API y quedan abiertos para
decisión humana, ver más abajo.

`contract-tester`: 69 pruebas en nueve archivos, más `conftest.py` y `helpers.py`. Los 34
criterios tienen al menos una prueba cuyo nombre empieza con su ID. Agregó pruebas para
requisitos del contrato sin criterio `CA` asociado (V-02, V-03, V-04, S-03 a S-07, S-10).
Deja sin prueba automática el comando de reinicio, la lectura de `RESERVAS_DB_PATH`, el
procedimiento manual del README y las restricciones del esquema, con el motivo de cada
exclusión.

**Hallazgo cruzado, que es la evidencia de que la separación sirvió.** La primera corrida
de la suite contra la implementación dio 31 fallas y 36 pasadas. Todas respondían a una
sola causa en producción: `src/reservas/api.py` tenía `from __future__ import annotations`
y sus dependencias (`require_unit`, `require_reservation`) eran funciones locales de
`create_app`. Con anotaciones diferidas, FastAPI 0.162.0 no resuelve esos nombres dentro de
`Annotated[..., Depends(...)]` y degrada el parámetro de ruta a query obligatorio: las tres
rutas con parámetro devolvían `422 VALIDATION_ERROR` con un `details` que reclamaba un
parámetro de query faltante, en lugar de los 200, 404 y 409 que exige la sección 7.3.
`contract-tester` reporta haberlo aislado con un repro mínimo ajeno al proyecto y no haber
debilitado ninguna prueba; `domain-builder` quitó la importación y dejó el motivo
documentado en el docstring del módulo para que nadie la reponga.

Las pruebas del propio implementador no habrían bastado para encontrarlo: su script de
verificación recorre los mismos 34 criterios y lo detectó en la misma corrida, pero fue la
suite independiente la que lo acotó a una causa única. `contract-tester` anota además una
prueba que el bug no habría hecho fallar, porque el código esperado ahí también es
`VALIDATION_ERROR`.

### Verificado por la sesión principal

Ejecutado después de que los dos agentes terminaran, desde un estado limpio
(`.pytest_cache` y `__pycache__` borrados):

| Comando | Resultado |
|---|---|
| `.venv/Scripts/python -m pytest -q` | `69 passed, 1 warning in 3.33s` |
| `.venv/Scripts/python -m pytest -q --collect-only`, nombres cruzados contra la lista de criterios | 34 de 34 criterios con prueba propia, ninguno faltante |
| `grep` de `intervals_overlap` y de comparaciones de intervalo en `src/` | Una sola definición, en `domain.py`. El único otro lugar es el `CHECK (start_at < end_at)` del esquema, que la sección 8 declara respaldo |
| `grep` de `DELETE FROM` y `DROP TABLE` en `src/` | Ninguno, consistente con R-08 |
| `grep` de `sys.modules`, `monkeypatch`, `Mock` y escrituras a `src/` en `tests/` | Ninguno. No hay stubs ni dobles |
| `git status --short` | Solo `README.md`, `src/` y `tests/` como no rastreados. Sin commits |

Script propio de la sesión principal, independiente de `tests/`, que ejercita `create_app`
con el ejemplo canónico de la consigna: inventario de 5 unidades, creación de MIC-01 10:00
a 11:00 normalizada a 13:00Z a 14:00Z, rechazo de 10:30 a 11:30 con `409 OVERLAP` y
`details` apuntando a la base, aceptación de 11:00 a 12:00 y de MIC-02 en el mismo horario,
coincidencia entre consulta y creación (R-07), y cancelación que libera el horario y
conserva el registro en el historial. Resultado: todo ok.

Nota sobre ese script: su primera versión dio dos fallas, y eran del script, no del código.
Consultaba disponibilidad de 13:30Z a 14:30Z en una base donde ella misma había creado
antes MIC-01 de 14:00Z a 15:00Z, que se superpone de forma legítima con el intervalo
consultado. Se corrigió aislando cada bloque en su propia base. Queda anotado porque es
exactamente el error que las pruebas escritas por el implementador tienden a cometer:
ajustar la expectativa al estado que el propio script dejó.

El único warning de la suite es ajeno al proyecto:
`StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated`,
emitido por `fastapi/testclient.py` con starlette 1.10.0. Resolverlo exigiría agregar
`httpx2`, dependencia que la spec no lista.

### Puntos abiertos que requieren decisión humana

`domain-builder` los separó de lo verificado porque la spec no los fija, y son observables
desde la API:

1. En `GET /units/{unit_id}/availability`, `404 UNIT_NOT_FOUND` tiene precedencia sobre el
   `422 VALIDATION_ERROR` de `start` o `end`. La sección 7.4 fija el orden de evaluación
   solo para la creación; la tabla de 7.3 lista el 404 primero. Se invierte moviendo la
   búsqueda de la unidad al cuerpo del handler.
2. En `GET /reservations`, `unit_id` vacío se trata como unidad inexistente y devuelve
   `422 UNKNOWN_UNIT`, y `status` vacío devuelve `422 VALIDATION_ERROR`. Es la lectura
   literal de V-01 y de la sección 7.4, no la convención tolerante de "vacío equivale a
   ausente".

### Decisión del humano y motivo

**Decisión.** Los dos comportamientos quedan tal cual están: no se toca el código. Se
documentan en `docs/spec.md` como supuestos S-11 y S-12, con los criterios CA-35 y CA-36, y
la versión del contrato sube a 1.1.0.

**Motivo, dictado por el humano.** Transcripción literal, con los acentos restituidos:

> La spec dice que el contrato congelado se cambia al subir la versión; dejarlo sin
> documentar siendo observable desde la API es algo que el congelado intenta cerrar. El
> costo sería que la tabla de criterios queda incompleta hasta que `contract-tester`
> agregue CA-35 y CA-36.

**Consecuencia.** El cambio de 1.0.0 a 1.1.0 es de documentación: agrega dos supuestos y
dos criterios, no altera ninguna respuesta de la API y no invalida ninguna de las 69
pruebas existentes. La sección 10 declara que cada criterio tiene al menos una prueba, y
CA-35 y CA-36 son la excepción vigente hasta que `contract-tester` las escriba; queda
anotado en la propia sección 10 para que el hueco no sea silencioso.
