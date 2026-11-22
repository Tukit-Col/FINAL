"""Migraciones, deriva y contrato HTTP contra el stack vivo.

NFR-MAN-03: cada base esta en la cabeza de la historia de SU servicio y el
esquema migrado dice lo mismo que los modelos (`arquitectura/verificar_deriva.py`,
el mismo paso del job `migraciones`). Las bases del stack se crean solo con
migraciones, como en CI, asi que lo que falte en una revision se ve aqui.

NFR-MAN-04: las rutas de `docs/arquitectura/CONTRATO_API.md` contra las que sirve
cada servicio segun su `openapi.json`, y cada ruta servida llega por la puerta
al servicio que la atiende.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

import httpx
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from stack_vivo import GATEWAY, RAIZ, SERVICIOS_CON_BASE, conexion_a
from tukit_gateway.api import bloqueada, destino

pytestmark = pytest.mark.integracion

# --------------------------------------------------------------- NFR-MAN-03


def _cabezas(servicio: str) -> set[str]:
    # Sin leer `alembic.ini`: su `prepend_sys_path` sin `path_separator` avisa
    # con un DeprecationWarning, y para listar revisiones basta la carpeta.
    config = Config()
    config.set_main_option("script_location", str(RAIZ / "servicios" / servicio / "migraciones"))
    return set(ScriptDirectory.from_config(config).get_heads())


@pytest.mark.nfr("NFR-MAN-03")
@pytest.mark.parametrize("servicio", SERVICIOS_CON_BASE)
async def test_la_base_esta_en_la_cabeza_de_su_historia(servicio: str, record_property):
    async with conexion_a(servicio) as conexion:
        en_la_base = {
            fila[0] for fila in await conexion.execute(text("select version_num from alembic_version"))
        }

    record_property("revision", ",".join(sorted(en_la_base)))
    assert en_la_base == _cabezas(servicio)


@pytest.fixture(scope="module")
def deriva() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "arquitectura/verificar_deriva.py"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.mark.nfr("NFR-MAN-03")
def test_el_verificador_de_deriva_llega_a_las_cinco_bases(deriva: subprocess.CompletedProcess[str]):
    """Control: sale con 0 o 1 (no con 2, que es no poder conectarse) y opina de todas."""
    assert deriva.returncode in (0, 1), deriva.stdout + deriva.stderr
    for servicio in SERVICIOS_CON_BASE:
        assert re.search(rf"(ok|DERIVA) +{servicio}:", deriva.stdout), deriva.stdout


# El catalogo salio de H-A-60 en `b6b6fe7`: dfc4fd3 declara en el modelo el `server_default` de
# `concepto.uno_por_estudiante` y de `item_lista_oficial.avisos_descartados` (N-176).
@pytest.mark.nfr("NFR-MAN-03")
@pytest.mark.parametrize("servicio", SERVICIOS_CON_BASE)
def test_el_esquema_migrado_coincide_con_los_modelos(
    deriva: subprocess.CompletedProcess[str], servicio: str, record_property
):
    """Por servicio. En inteligencia es el control de no regresion de H-A-01: desde c57c0b3 la
    migracion `20260928_1900_tabla_kit_canonico.py` crea `kit_canonico`."""
    record_property("salida_deriva", " | ".join(deriva.stdout.split("\n")[:8]))
    assert re.search(rf"ok +{servicio}:", deriva.stdout), deriva.stdout


@pytest.mark.nfr("NFR-MAN-03")
def test_los_grados_canonicos_responden_sobre_una_base_migrada(cliente: httpx.Client):
    """Control de no regresion de H-A-01: con `kit_canonico` migrada (c57c0b3), 200 y no 500."""
    respuesta = cliente.get("/v1/grados-canonicos")

    assert respuesta.status_code == 200, respuesta.text[:200]
    assert isinstance(respuesta.json()["grados"], list)


# --------------------------------------------------------------- NFR-MAN-04

_METODOS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _forma(camino: str) -> str:
    """El camino sin consulta ni barra final y con cada parametro como `{}`."""
    return re.sub(r"\{[^}]+\}", "{}", camino.split("?")[0].rstrip("/"))


def _documentadas() -> set[tuple[str, str]]:
    # En `docs/arquitectura/` desde b96a7df (antes, `arquitectura/`).
    contrato = (RAIZ / "docs" / "arquitectura" / "CONTRATO_API.md").read_text()
    return {(m, _forma(p)) for m, p in re.findall(r"`(GET|POST|PUT|PATCH|DELETE) (/v1/[^`\s]*)`", contrato)}


@pytest.fixture(scope="module")
def servidas(stack: dict[str, Any]) -> dict[tuple[str, str], tuple[str, str]]:
    """`(metodo, forma) -> (servicio, camino)` de cada ruta `/v1` que publica el stack."""
    fuentes = {nombre: datos["url"] for nombre, datos in stack["servicios"].items()}
    fuentes["gateway"] = GATEWAY
    rutas: dict[tuple[str, str], tuple[str, str]] = {}
    for servicio, base in fuentes.items():
        documento = httpx.get(f"{base}/openapi.json", timeout=30).json()
        for camino, operaciones in documento["paths"].items():
            for metodo in operaciones:
                if metodo.upper() in _METODOS and camino.startswith("/v1/"):
                    rutas[(metodo.upper(), _forma(camino))] = (servicio, camino)
    return rutas


@pytest.mark.nfr("NFR-MAN-04")
def test_cada_ruta_servida_llega_por_la_puerta_a_su_servicio(servidas: dict, record_property):
    mal_ruteadas = [
        f"{metodo} {camino}: {servicio} -> {destino(camino)}"
        for (metodo, _), (servicio, camino) in servidas.items()
        if servicio != "gateway" and not bloqueada(camino) and destino(camino) != servicio
    ]

    record_property("rutas_servidas", len(servidas))
    assert len(servidas) > 0
    assert mal_ruteadas == []


@pytest.mark.nfr("NFR-MAN-04")
@pytest.mark.xfail(strict=True, reason="H-C-13: el contrato documenta rutas que ningun servicio sirve")
def test_cada_ruta_del_contrato_la_sirve_algun_servicio(servidas: dict, record_property):
    faltan = sorted(f"{m} {p}" for m, p in _documentadas() - set(servidas))

    record_property("documentadas_no_servidas", ";".join(faltan) or "0")
    assert faltan == []


@pytest.mark.nfr("NFR-MAN-04")
@pytest.mark.xfail(strict=True, reason="H-C-13: el contrato no documenta la mayoria de las rutas servidas")
def test_cada_ruta_servida_esta_en_el_contrato(servidas: dict, record_property):
    sin_documentar = sorted(f"{m} {servidas[(m, p)][1]}" for m, p in set(servidas) - _documentadas())

    record_property("servidas_sin_documentar", len(sin_documentar))
    assert sin_documentar == [], f"{len(sin_documentar)} rutas sin documentar, p. ej. {sin_documentar[:5]}"
