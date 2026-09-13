"""Shared test setup.

WHY: El esquema SQLite se crea en el ``lifespan`` de FastAPI, que sólo se ejecuta si el
``TestClient`` se usa como context manager.  Varias pruebas instancian el cliente
directamente, así que funcionaban únicamente porque otra prueba de la misma sesión había
creado ya la base de datos.

Eso hacía que la suite completa pasara pero ejecutar un solo archivo fallara con
``no such table: engraving_jobs`` en una instalación limpia — un error desconcertante para
quien mantiene el proyecto y que se descubrió al verificar el paquete 0.7.0 sobre un árbol
sin base de datos previa.

Inicializar el esquema una vez por sesión elimina la dependencia de orden entre archivos.
"""

from __future__ import annotations

import pytest

from app.db import init_db


# WHY: Autouse y de sesión: ninguna prueba debe tener que acordarse de pedirlo.
@pytest.fixture(scope="session", autouse=True)
def _database_schema_ready() -> None:
    init_db()
