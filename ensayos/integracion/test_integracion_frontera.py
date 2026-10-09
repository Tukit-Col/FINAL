"""La frontera de cumplimiento de identidad, vista en el Postgres del stack vivo.

P2 (ATAM:532-535) y DN-08: identidad corre en su propio proceso con su propia
base, y ningun otro servicio la lee. Las fronteras de importacion ya las cubre
NFR-MAN-02 (`arquitectura/`); aqui se mira lo que pasa en tiempo de ejecucion:
quien tiene abierta una conexion a la base de identidad mientras el stack
atiende trafico, y si las credenciales de otro servicio bastan para entrar.

Cada conexion de `pg_stat_activity` se atribuye a un proceso del stack por su
puerto cliente con `lsof` y los `.pid` que deja `make arriba`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from collections import Counter

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from stack_vivo import CLAVE_DEMO, USUARIOS_DEMO, conexion_a, procesos_del_stack
from tukit_comun.config import url_desde_entorno

pytestmark = pytest.mark.integracion

# Los dos procesos de `make arriba` que pertenecen a identidad.
_DUENOS_DE_IDENTIDAD = {"identidad", "poller-identidad"}
_MUESTRAS = 12


def _base_de(servicio: str) -> str:
    return make_url(url_desde_entorno(servicio)).database


def _puertos_cliente() -> dict[int, int]:
    """`puerto cliente -> pid` de cada conexion TCP establecida contra el 5432."""
    if shutil.which("lsof") is None:
        pytest.fail("hace falta `lsof` para atribuir cada conexion a un proceso")
    salida = subprocess.run(
        ["lsof", "-nP", "-iTCP:5432", "-sTCP:ESTABLISHED", "-Fpn"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    puertos: dict[int, int] = {}
    pid = 0
    for linea in salida.splitlines():
        if linea.startswith("p"):
            pid = int(linea[1:])
        elif linea.startswith("n") and (encontrado := re.search(r":(\d+)->", linea)):
            puertos[int(encontrado.group(1))] = pid
    return puertos


def _trafico(http: httpx.Client) -> None:
    """Un poco de todo: sesion (identidad), catalogo, inteligencia y comercio."""
    entrada = http.post(
        "/v1/sesiones", json={"correo": USUARIOS_DEMO["acudiente"], "clave": CLAVE_DEMO}
    ).json()
    cabeceras = {"authorization": f"Bearer {entrada['token']}"}
    http.get("/v1/cuenta", headers=cabeceras)
    http.get("/v1/colegios")
    http.get("/v1/catalogo/productos", params={"por_pagina": 5})
    http.get("/v1/mis-solicitudes", headers=cabeceras)
    http.get(
        "/v1/comercio/mis-pedidos", params={"usuario_id": entrada["sesion"]["usuario_id"]}, headers=cabeceras
    )


@pytest.mark.nfr("NFR-SEG-08")
async def test_solo_los_procesos_de_identidad_abren_su_base(cliente: httpx.Client, record_property):
    base = _base_de("identidad")
    procesos = procesos_del_stack()
    propio = os.getpid()
    vistos: Counter[str] = Counter()
    # La vista se consulta desde la base de operacion para no sumar una
    # conexion propia a la de identidad.
    async with conexion_a("operacion") as conexion:
        for _ in range(_MUESTRAS):
            _trafico(cliente)
            filas = (
                await conexion.execute(
                    text(
                        "select client_port from pg_stat_activity "
                        "where datname = :base and client_port is not null and pid <> pg_backend_pid()"
                    ),
                    {"base": base},
                )
            ).all()
            await conexion.commit()
            puertos = _puertos_cliente()
            for (puerto,) in filas:
                pid = puertos.get(puerto)
                if pid != propio:
                    vistos[procesos.get(pid, f"pid-{pid}")] += 1
            time.sleep(0.5)

    record_property("muestras", _MUESTRAS)
    record_property("conexiones_por_proceso", ";".join(f"{n}:{c}" for n, c in sorted(vistos.items())))
    assert vistos, f"ninguna conexion a {base} en {_MUESTRAS} muestras: el barrido no vio nada"
    assert set(vistos) <= _DUENOS_DE_IDENTIDAD, dict(vistos)


async def _usuarios_visibles(url: str) -> int | None:
    """Cuantos usuarios se leen con esa URL, o None si Postgres lo niega."""
    motor = create_async_engine(url)
    try:
        async with motor.connect() as conexion:
            return (await conexion.execute(text("select count(*) from usuario"))).scalar_one()
    except DBAPIError:
        return None
    finally:
        await motor.dispose()


@pytest.mark.nfr("NFR-SEG-08")
async def test_las_credenciales_de_identidad_leen_su_base():
    """Control: la consulta del ensayo de abajo funciona con las credenciales propias."""
    assert await _usuarios_visibles(url_desde_entorno("identidad")) is not None


@pytest.mark.nfr("NFR-SEG-08")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "H-A-34: las cinco bases comparten el rol `tukit`; "
        "con la URL de cualquier otro servicio se leen los usuarios de identidad"
    ),
)
@pytest.mark.parametrize("servicio", ["catalogo", "inteligencia", "comercio", "operacion"])
async def test_las_credenciales_de_otro_servicio_no_abren_la_base_de_identidad(
    servicio: str, record_property
):
    ajena = make_url(url_desde_entorno(servicio)).set(database=_base_de("identidad"))
    leidos = await _usuarios_visibles(ajena.render_as_string(hide_password=False))

    record_property("usuarios_leidos", "negado" if leidos is None else leidos)
    assert leidos is None, f"con las credenciales de {servicio} se leen {leidos} usuarios de identidad"
