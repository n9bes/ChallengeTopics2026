"""Fixtures de las pruebas de contrato.

Propósito: construir la aplicación real descrita en la sección 7.1 de `docs/spec.md`
sobre una base SQLite temporal y con el reloj de referencia de la sección 10.

Invariantes:
- Cada prueba recibe un `db_path` propio dentro de `tmp_path`; nunca se toca `data/`.
- El reloj está congelado en `2026-11-02T12:00:00Z` (S-08).
- `TestClient` se usa siempre como gestor de contexto.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from helpers import CLOCK_NOW
from reservas.api import create_app


@pytest.fixture
def fixed_clock() -> Callable[[], datetime]:
    """Reloj inyectable (S-08) congelado en el reloj de referencia."""

    def clock() -> datetime:
        return CLOCK_NOW

    return clock


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Archivo SQLite temporal. Jamás la base real del proyecto."""
    return tmp_path / "reservas_test.db"


@pytest.fixture
def make_app(db_path: Path, fixed_clock: Callable[[], datetime]) -> Callable[[], FastAPI]:
    """Construye aplicaciones sobre el mismo archivo: equivale a reiniciar el servidor."""

    def factory() -> FastAPI:
        return create_app(db_path=db_path, clock=fixed_clock)

    return factory


@pytest.fixture
def client(make_app: Callable[[], FastAPI]) -> Iterator[TestClient]:
    """Cliente sobre una base recién creada y vacía de reservas."""
    with TestClient(make_app()) as test_client:
        yield test_client
