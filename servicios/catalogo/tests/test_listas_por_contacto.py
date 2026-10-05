"""El endpoint interno `GET /interno/listas-por-contacto/{usuario_id}`.

Es la lectura servicio-a-servicio que alimenta "Mis solicitudes" del acudiente:
Inteligencia le pega directo a Catalogo con el `usuario_id` de la sesion que ya
valido. Vive fuera de `/v1/` A PROPOSITO —la puerta no rutea `/interno`—, asi
que no existe hacia el navegador.

Lo que protegen las pruebas: devuelve solo las tareas del contacto pedido (jamas
las de otro), deduplica una version que tiene varias tareas en una sola fila
(gana la mas reciente), saca `colegio_nombre` de `colegio_datos` (y es `None`
para un colegio aliado), y expone `revisada_en` de la version unida para que
Inteligencia distinga aprobada de recibida.

Corre con `ASGITransport` y un SQLite inyectado por `app.state`, igual que
`test_api_admin`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_catalogo.api import app
from tukit_catalogo.modelos import (
    Base,
    ListaOficial,
    TareaImportacion,
    VersionListaOficial,
)
from tukit_comun.bd import MotorServicio

COLEGIO = uuid.UUID("11111111-1111-5111-8111-111111111111")
PADRE = uuid.UUID("aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa")
OTRO_PADRE = uuid.UUID("bbbbbbbb-bbbb-5bbb-8bbb-bbbbbbbbbbbb")


def _tarea(sesion, *, contacto, version_id=None, colegio_datos=None, grado="Quinto", creada_en=None):
    tarea = TareaImportacion(
        origen="onboarding",
        estado="completada",
        contacto_referencia=contacto,
        colegio_id=COLEGIO,
        grado=grado,
        anio_lectivo=2026,
        version_id=version_id,
        colegio_datos=colegio_datos,
    )
    sesion.add(tarea)
    sesion.flush()
    if creada_en is not None:
        tarea.creada_en = creada_en
        sesion.flush()
    return tarea


def _version_revisada(sesion, revisada_en):
    """Una version YA REVISADA (con su lista), para el caso `aprobada`."""
    lista = ListaOficial(colegio_id=COLEGIO, grado="Quinto", anio_lectivo=2026)
    sesion.add(lista)
    sesion.flush()
    version = VersionListaOficial(lista_id=lista.id, numero=1, revisada_en=revisada_en)
    sesion.add(version)
    sesion.flush()
    return version


def _siembra(sesion) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}

    # Una version aprobada del padre, con dos tareas (dedup a una fila).
    version = _version_revisada(sesion, datetime(2026, 2, 1, 12, 0, tzinfo=UTC))
    ids["version"] = version.id
    _tarea(sesion, contacto=PADRE, version_id=version.id, creada_en=datetime(2026, 1, 1, 9, 0, tzinfo=UTC))
    _tarea(sesion, contacto=PADRE, version_id=version.id, creada_en=datetime(2026, 1, 2, 9, 0, tzinfo=UTC))

    # Una tarea sin version (sugerencia aun pendiente), de colegio nuevo: sale
    # con su `colegio_nombre` de `colegio_datos` y sin `version_id`.
    _tarea(
        sesion,
        contacto=PADRE,
        version_id=None,
        grado="Tercero",
        colegio_datos={"nombre": "Colegio Nuevo", "dane": "123"},
    )

    # Una tarea de OTRO contacto: nunca debe aparecer.
    _tarea(sesion, contacto=OTRO_PADRE, version_id=None, grado="Cuarto")

    return ids


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    ids: dict[str, uuid.UUID] = {}
    async with fabrica() as sesion:
        ids = await sesion.run_sync(lambda s: _siembra(s))
        await sesion.commit()
    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        http.ids = ids  # type: ignore[attr-defined]
        yield http
    await engine.dispose()


async def test_devuelve_solo_las_del_contacto(cliente):
    cuerpo = (await cliente.get(f"/interno/listas-por-contacto/{PADRE}")).json()
    # Dos versiones distintas del padre: la aprobada (deduplicada de dos tareas)
    # y la sugerencia sin version. Nada del otro contacto.
    assert len(cuerpo["listas"]) == 2
    grados = {fila["grado"] for fila in cuerpo["listas"]}
    assert grados == {"Quinto", "Tercero"}


async def test_ignora_otros_contactos(cliente):
    cuerpo = (await cliente.get(f"/interno/listas-por-contacto/{OTRO_PADRE}")).json()
    assert len(cuerpo["listas"]) == 1
    assert cuerpo["listas"][0]["grado"] == "Cuarto"


async def test_dedup_por_version_id(cliente):
    cuerpo = (await cliente.get(f"/interno/listas-por-contacto/{PADRE}")).json()
    version_id = str(cliente.ids["version"])
    de_version = [fila for fila in cuerpo["listas"] if fila["version_id"] == version_id]
    assert len(de_version) == 1  # dos tareas, una sola fila
    # La version esta revisada: `revisada_en` viaja para que Inteligencia la
    # clasifique como aprobada.
    assert de_version[0]["revisada_en"] is not None


async def test_colegio_nombre_de_colegio_datos(cliente):
    cuerpo = (await cliente.get(f"/interno/listas-por-contacto/{PADRE}")).json()
    por_grado = {fila["grado"]: fila for fila in cuerpo["listas"]}
    # Colegio nuevo: el nombre viene de colegio_datos.
    assert por_grado["Tercero"]["colegio_nombre"] == "Colegio Nuevo"
    assert por_grado["Tercero"]["version_id"] is None
    # Colegio aliado (sin colegio_datos): el nombre vive en identidad -> None.
    assert por_grado["Quinto"]["colegio_nombre"] is None


async def test_cada_fila_trae_su_tarea_para_poder_retirarla(cliente):
    cuerpo = (await cliente.get(f"/interno/listas-por-contacto/{PADRE}")).json()
    assert all(fila["tarea_id"] for fila in cuerpo["listas"])


async def test_retirar_desvincula_toda_la_version_y_solo_del_contacto(cliente):
    """El acudiente cancela su solicitud: sus tareas de esa version dejan de ser
    suyas (las dos, no solo la que se ve), la lista sigue en la cola del colegio,
    y las listas de otro acudiente no se tocan."""
    cuerpo = (await cliente.get(f"/interno/listas-por-contacto/{PADRE}")).json()
    version_id = str(cliente.ids["version"])
    fila = next(f for f in cuerpo["listas"] if f["version_id"] == version_id)

    respuesta = await cliente.post(
        f"/interno/listas-por-contacto/{PADRE}/retirar", json={"tarea_id": fila["tarea_id"]}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["retiradas"] == 2

    quedan = (await cliente.get(f"/interno/listas-por-contacto/{PADRE}")).json()["listas"]
    assert [f["grado"] for f in quedan] == ["Tercero"]
    otro = (await cliente.get(f"/interno/listas-por-contacto/{OTRO_PADRE}")).json()["listas"]
    assert len(otro) == 1


async def test_retirar_la_tarea_de_otro_no_hace_nada(cliente):
    del_otro = (await cliente.get(f"/interno/listas-por-contacto/{OTRO_PADRE}")).json()["listas"][0]
    respuesta = await cliente.post(
        f"/interno/listas-por-contacto/{PADRE}/retirar", json={"tarea_id": del_otro["tarea_id"]}
    )
    assert respuesta.json()["retiradas"] == 0
    assert len((await cliente.get(f"/interno/listas-por-contacto/{OTRO_PADRE}")).json()["listas"]) == 1


async def test_retirar_por_version(cliente):
    respuesta = await cliente.post(
        f"/interno/listas-por-contacto/{PADRE}/retirar", json={"version_id": str(cliente.ids["version"])}
    )
    assert respuesta.json()["retiradas"] == 2
