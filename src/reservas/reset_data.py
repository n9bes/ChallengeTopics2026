"""Reinicio de datos: borra el archivo de la base y con el todas las reservas.

Corresponde a la seccion 8 de `docs/spec.md`. El borrado es destructivo e irreversible:
se van las reservas activas y las canceladas. Por eso pide confirmacion explicita y hay
que escribir la palabra completa, no una tecla.

Uso, desde la raiz del repositorio:

    .venv/Scripts/python src/reservas/reset_data.py
    .venv/Scripts/python src/reservas/reset_data.py --db-path otra/ruta.db
    .venv/Scripts/python src/reservas/reset_data.py --yes   # sin preguntar

Codigos de salida: 0 si borro o si no habia nada que borrar, 1 si el usuario cancelo,
2 si la ruta existe y no es un archivo.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

if __package__ in (None, ""):  # ejecucion como script: python src/reservas/reset_data.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reservas.config import DB_PATH_ENV_VAR, resolve_db_path  # noqa: E402

CONFIRMATION_WORD = "BORRAR"
"""Palabra que hay que escribir para confirmar el borrado."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reset_data",
        description=(
            "Borra el archivo SQLite de reservas. Elimina todas las reservas, "
            "activas y canceladas."
        ),
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help=f"Ruta del archivo. Por defecto, {DB_PATH_ENV_VAR} o data/reservas.db.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma sin preguntar. Solo para uso no interactivo.",
    )
    return parser


def confirm(db_path: Path, *, read_line: Callable[[str], str] = input) -> bool:
    """Pide la confirmacion explicita por entrada estandar.

    Entrada: la ruta a borrar. Salida: `True` solo si se escribio la palabra exacta.
    """
    print(f"Se va a borrar el archivo: {db_path.resolve()}")
    print("Se pierden TODAS las reservas, activas y canceladas. No se puede deshacer.")
    prompt = f"Para confirmar, escriba {CONFIRMATION_WORD}: "
    try:
        answer = read_line(prompt)
    except EOFError:
        return False
    return answer.strip() == CONFIRMATION_WORD


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    db_path: Path = arguments.db_path or resolve_db_path()

    if not db_path.exists():
        print(f"No hay nada que borrar: {db_path.resolve()} no existe.")
        return 0
    if not db_path.is_file():
        print(f"La ruta {db_path.resolve()} no es un archivo. No se borra nada.")
        return 2
    if not arguments.yes and not confirm(db_path):
        print("Cancelado. No se borro nada.")
        return 1

    db_path.unlink()
    print(f"Listo. Se borro {db_path.resolve()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
