# Preparación del agente

Este archivo es la evidencia versionada de cómo se preparó y se usó el agente de
programación.

La configuración del agente que aplica a este proyecto está versionada en el repositorio y
es inspeccionable de forma directa: `CLAUDE.md` en la raíz y `.claude/agents/`. Lo único
que no se versiona es `.claude/settings.local.json`, que contiene rutas de la máquina y
permisos concedidos, y la configuración personal del autor, que vive fuera del repositorio
y se resume saneada más abajo. Ver [Qué se excluye y por qué](#qué-se-excluye-y-por-qué).

Estado: ya no quedan secciones marcadas con `PENDIENTE`. Del flujo descrito más abajo falta
solo la revisión final con `/code-review`. No se registra como hecho nada que no se haya
ejecutado.

## Entorno y modelo

| Dato | Valor | Cómo se obtuvo |
|---|---|---|
| Harness | Claude Code, pestaña Code de la app de escritorio de Claude | Entorno de trabajo |
| Versión del harness | 2.1.202 | `claude --version` |
| Modelo | Opus 5, identificador `claude-opus-5` | Expuesto por el harness en la sesión |
| Sistema operativo | Windows 11 Pro 10.0.26200 | Entorno de trabajo |
| Shell | PowerShell 5.1 y Git Bash | Entorno de trabajo |
| Git | 2.51.0.windows.2 | `git --version` |
| Python | 3.11.9 | `python --version` |

Motivo de la elección: el harness ya estaba disponible y opera sobre el repositorio con
herramientas reales (lectura y escritura de archivos, ejecución de comandos, git), que es
lo que pide la consigna. No se construyó un harness propio.

Dato no visible: el harness no expone un identificador de build del modelo más preciso que
`claude-opus-5`. No se infiere ninguno.

## Instrucciones realmente usadas

### Instrucciones a nivel proyecto

Archivo: [`CLAUDE.md`](../CLAUDE.md) en la raíz del repositorio, versionado. Se tomó de
`https://raw.githubusercontent.com/drona23/claude-token-efficient/main/CLAUDE.md`
(352 bytes). Se reproduce abajo por comodidad; el archivo versionado es la fuente:

```markdown
## Approach
- Read existing files before writing. Don't re-read unless changed.
- Thorough in reasoning, concise in output.
- Skip files over 100KB unless required.
- No sycophantic openers or closing fluff.
- No emojis or em-dashes.
- Do not guess APIs, versions, flags, commit SHAs, or package names. Verify by reading code or docs before asserting.
```

Cómo se aplicó: el harness carga este archivo automáticamente al iniciar la sesión en este
directorio. La última regla es la que más impacto tuvo en el trabajo: obligó a verificar las
versiones de la tabla de arriba con comandos reales en lugar de declararlas de memoria.

### Instrucciones a nivel usuario

Archivo: `~/.claude/CLAUDE.md`, externo al repositorio y fuera del alcance de la entrega.
Es configuración personal, aplicada a todos los proyectos del autor. No se reproduce.
Resumen saneado de lo que aporta a esta sesión, sin volcar el texto:

- Prioriza mantenibilidad, legibilidad y corrección por sobre velocidad.
- Exige preguntar ante requisitos ambiguos en lugar de asumirlos.
- Prohíbe crear commits automáticamente. Los commits los decide el humano.
- Pide Conventional Commits cuando se prepara uno.
- Pide pruebas y prohíbe borrar pruebas para que el conjunto pase.
- Prohíbe exponer secretos o credenciales.

Cómo se aplicó: la regla de no commitear automáticamente es la que gobierna el flujo de
trabajo de todo el challenge. Todos los commits de este repositorio son decisión humana
explícita.

## Contexto suministrado

| Qué se suministró | Forma |
|---|---|
| `challenge-agents.pdf` | Leído completo por el agente, 3 páginas |
| Inventario de unidades | Contenido en el PDF, página 1 |
| Reglas de solapamiento y ejemplo MIC-01 | Contenido en el PDF, página 1 |
| Rúbrica de evaluación | Contenido en el PDF, página 3 |

## Qué se excluye y por qué

| Excluido | Motivo |
|---|---|
| `~/.claude/CLAUDE.md` | Configuración personal del autor, aplica a todos sus proyectos, no es parte de esta entrega. Vive fuera del repositorio. Se incluye el resumen saneado de arriba. |
| Memoria del agente (`~/.claude/projects/.../memory/`) | Preferencias personales de trabajo, externas al repositorio. |
| `.claude/settings.local.json` | Única exclusión activa del `.gitignore`. Contiene permisos concedidos y rutas de esta máquina, que no son reproducibles ni necesarios para terceros. |
| Transcripciones completas de la sesión | La consigna lo prohíbe de forma explícita. Se registran episodios puntuales con su evidencia. |
| Correo y rutas locales de la máquina | Dato personal, sin valor para la reproducción. |

Nada de lo excluido es necesario para reproducir la aplicación ni sus pruebas.

Nota sobre esta decisión: la versión inicial del `.gitignore` excluía `CLAUDE.md` y
`.claude/` por completo. Se revirtió al verificar que lo único que ocultaba era un archivo
público sin datos del autor, mientras bloqueaba la evidencia de preparación que la consigna
pide. Queda registrado en `docs/decisions.md`.

## Herramientas y acciones permitidas

| Herramienta | Alcance concedido |
|---|---|
| Lectura de archivos | Todo el repositorio |
| Escritura de archivos | Todo el repositorio |
| Ejecución de comandos | Shell local, con clasificador de permisos activo |
| Red | Solo lectura de URLs indicadas por el humano |
| Git | Lectura de estado e historial. Commits reservados al humano. |

### Controles aplicados

Control 1. Clasificador de permisos del harness, modo automático.

Evento real: al intentar descargar el `CLAUDE.md` remoto directamente sobre el disco con
`curl -o CLAUDE.md <url>`, el clasificador rechazó la acción con el motivo
`Instruction Poisoning`. El razonamiento del control es correcto: escribir instrucciones
traídas de un tercero directamente como configuración del agente, sin revisión, es un vector
de inyección.

Resolución humana: se descargó el contenido a salida estándar, se revisó completo (352 bytes,
6 reglas de estilo, sin instrucciones de ejecución ni referencias externas) y recién entonces
se escribió el archivo de forma explícita. Queda registrado como episodio de delegación.

Control 2. Ningún commit automático. Todos los commits del repositorio son decisión humana.

Control 3. Separación entre quien implementa y quien prueba. Las pruebas se derivan de la
especificación, no de la implementación, para que un error del dominio no quede justificado
por una prueba escrita a su medida. Se materializa en dos subagentes distintos, ver abajo.

Control 4. [`.claude/settings.json`](../.claude/settings.json), versionado, declara
`git commit` y `git push` como reglas `ask`. Cualquier intento, de la sesión principal o de
un subagente, requiere aprobación humana explícita. Según la documentación de Claude Code,
las reglas `ask` aplican de inmediato, sin esperar la confianza del directorio.

## Subagentes del proyecto

Definidos en [`.claude/agents/`](../.claude/agents/), versionados. Formato verificado contra
la documentación oficial de subagentes de Claude Code.

| Agente | Responsabilidad | Escribe en | Modelo |
|---|---|---|---|
| [`domain-builder`](../.claude/agents/domain-builder.md) | Dominio, persistencia SQLite, API FastAPI | código de producción | el de la sesión |
| [`contract-tester`](../.claude/agents/contract-tester.md) | Pruebas derivadas solo de la spec | `tests/` | el de la sesión |
| [`frontend-builder`](../.claude/agents/frontend-builder.md) | UI mínima estática. Diferido, ver D-004 | directorio web | `sonnet` |

Ninguno tiene la herramienta `Agent`, así que no pueden lanzar subagentes propios. Todos se
detienen si `docs/spec.md` no existe o no tiene el contrato congelado.

Limitación observada el 2026-10-24: los archivos de `.claude/agents/` se crearon durante una
sesión ya iniciada, y al intentar delegar en esa misma sesión el harness respondió
`Agent type 'domain-builder' not found`, listando solo los agentes integrados. Los
subagentes de proyecto se cargan al iniciar la sesión. No se sustituyeron por un agente
genérico con las instrucciones pegadas, porque así no se aplicarían las restricciones de
herramientas de cada definición.

Resolución, el mismo 2026-10-24: en una sesión nueva los tres tipos aparecieron disponibles
y la delegación funcionó. `domain-builder` y `contract-tester` trabajaron en paralelo sobre
`src/reservas/` y `tests/`, y más tarde `contract-tester` recibió un segundo pedido para los
criterios CA-35 y CA-36. Queda confirmado que la condición es iniciar la sesión con los
archivos ya presentes; no hay nada que recargar. El detalle de esa delegación, con lo que
reportó cada agente y lo que verificó la sesión principal por su cuenta, está en el
episodio 1 de `docs/decisions.md`.

Trabajo que queda deliberadamente en la sesión principal, con el humano:

- **Especificación.** Requiere resolver ambigüedades con el humano, y los subagentes no
  tienen `AskUserQuestion`. Para explorar se usa el agente integrado `Plan`.
- **Registro de evidencia y episodios.** Un subagente no bifurcado arranca sin el historial
  de la conversación; reconstruir desde ahí las decisiones humanas invita a inventarlas.
- **Revisión de código.** Se usa la skill integrada `/code-review` en lugar de un revisor
  propio.

Orquestación: la sesión principal escribe la spec y congela el contrato (gate humano);
`domain-builder` y `contract-tester` trabajan en paralelo sobre directorios disjuntos;
la sesión principal integra y el humano corre las pruebas (gate humano); al final
`/code-review`. `frontend-builder` queda fuera de la orquestación mientras la UI esté diferida.

## Adaptación específica

La adaptación es la regla de límites consecutivos, que es donde más suele fallar una
implementación de reservas: con una reserva activa de 10:00 a 11:00, el intervalo 11:00 a
12:00 se acepta y 10:30 a 11:30 se rechaza. Es decir, intervalos semiabiertos
`[inicio, fin)` y comparación estricta, no `<=`.

Se instruyó una vez en la configuración versionada de los agentes, y quedó cubierta por
pruebas. Cadena completa, inspeccionable:

| Eslabón | Dónde |
|---|---|
| Instrucción al implementador | [`domain-builder.md`](../.claude/agents/domain-builder.md), en "Reglas del dominio que no se negocian": "10:00 a 11:00 y 11:00 a 12:00 no se superponen" |
| Instrucción al autor de pruebas | [`contract-tester.md`](../.claude/agents/contract-tester.md), en la cobertura mínima: "Límites consecutivos aceptados: 11:00 a 12:00 tras 10:00 a 11:00" |
| Regla en el contrato | `docs/spec.md`, R-02 y R-03, con su consecuencia escrita al final de la sección 4 |
| Criterios de aceptación | CA-03 y CA-07 de la sección 10, que son el par del ejemplo de la consigna |
| Pruebas | `tests/test_superposicion.py::test_ca03_rechaza_superposicion_parcial` y `tests/test_creacion.py::test_ca07_acepta_el_intervalo_inmediatamente_posterior`, más `test_ca08` para el límite anterior |
| Implementación | `src/reservas/domain.py`, función `intervals_overlap` |
| Commit de la implementación | `1122a9a` |
| Commit de las pruebas | `test: cubrir los 36 criterios de aceptación de la spec` |

Que la instrucción se aplicó, y no quedó en el papel, se ve en una consecuencia concreta:
`intervals_overlap` es la única definición de la regla en todo el código, y `storage.py` la
importa en lugar de reescribir la comparación en SQL. Reescribirla en SQL es la forma
habitual de que la regla termine duplicada y las dos copias divergan, que es exactamente lo
que R-07 prohíbe. Las pruebas de los dos límites pasan en la suite actual de 80.

## Retención del progreso

Las decisiones significativas y su motivo se registran en `docs/decisions.md`, versionado.
Este archivo se actualiza cuando cambia la preparación del agente, no al final del trabajo.
