"""Aplicacion para ejecucion normal.

    uvicorn reservas.main:app --app-dir src

La ruta de la base sale de `RESERVAS_DB_PATH`, con `data/reservas.db` por defecto, y el
reloj es el del sistema en UTC (seccion 7.1 de `docs/spec.md`).
"""

from __future__ import annotations

from fastapi import FastAPI

from reservas.api import create_app
from reservas.config import resolve_db_path, system_clock

app: FastAPI = create_app(db_path=resolve_db_path(), clock=system_clock)
