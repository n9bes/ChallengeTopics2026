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
