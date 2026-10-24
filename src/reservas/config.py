"""Configuracion de la ejecucion normal.

Corresponde a la seccion 7.1 de `docs/spec.md`: la ruta de la base sale de la variable
de entorno `RESERVAS_DB_PATH`, con `data/reservas.db` por defecto, y el reloj es el del
sistema en UTC.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

DB_PATH_ENV_VAR = "RESERVAS_DB_PATH"
"""Variable de entorno que fija la ruta del archivo SQLite."""

DEFAULT_DB_PATH = Path("data") / "reservas.db"
"""Ruta por defecto, relativa al directorio de trabajo."""


def resolve_db_path(environment: dict[str, str] | None = None) -> Path:
    """Devuelve la ruta de la base. Una variable vacia equivale a no estar definida."""
    source = os.environ if environment is None else environment
    configured = (source.get(DB_PATH_ENV_VAR) or "").strip()
    return Path(configured) if configured else DEFAULT_DB_PATH


def system_clock() -> datetime:
    """Momento actual del sistema en UTC (S-02)."""
    return datetime.now(timezone.utc)
