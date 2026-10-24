"""Sistema local de reservas de equipos de laboratorio.

Implementa el contrato congelado de `docs/spec.md` v1.0.0.

Capas:

- `models`: modelos del contrato (seccion 7.2).
- `errors`: codigos de error y sobre unico de las respuestas 4xx (seccion 7.4).
- `domain`: reglas de negocio y validaciones (secciones 4 y 5).
- `storage`: persistencia SQLite (seccion 8).
- `api`: fabrica `create_app` y endpoints (secciones 7.1 y 7.3).
- `config`: ruta de la base y reloj del sistema para la ejecucion normal.
- `main`: aplicacion que levanta uvicorn.
- `reset_data`: reinicio de datos con confirmacion explicita (seccion 8).
"""

__all__ = ["__version__"]

__version__ = "1.0.0"
