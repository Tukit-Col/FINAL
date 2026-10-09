"""NFR-MAN-01: el control de acceso de `/v1/admin` del catalogo (hallazgo H-C-06).

El gateway solo ENRUTA por prefijo (`/v1/admin/listas`, `/propuestas`,
`/catalogo`, `/sugerencias` van a catalogo) y no valida tokens; la validacion de
la sesion es de cada servicio. Inteligencia ya la hace en sus vistas de equipo
(`_exigir_staff`: 401 sin token o con token invalido, 403 si el rol no es
admin/operador) y el router de revision de catalogo nunca lee `Authorization`:
cualquiera que alcance el gateway puede editar, cerrar o borrar listas, leer los
PDF que subieron los acudientes (pueden traer nombres de menores) y aprobar
productos en el catalogo.

Estas pruebas escriben la conducta CORRECTA (sin testigo de staff, 401 o 403) y
estan marcadas como xfail estricto con el id H-C-06: hoy el router responde 2xx.
Cuando se agregue la puerta, el xfail estricto fallara y obligara a quitar la
marca. Se EXCLUYEN a proposito las rutas que Inteligencia consume de servicio a
servicio sin sesion de usuario (`importar`, `revision`, `resueltos`,
`POST /sugerencias`): exigirles staff las romperia sin un canal de credencial de
servicio, que el contrato no define; se reportan aparte.
"""

from __future__ import annotations

import base64
import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_catalogo.api import app
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    ItemListaOficial,
    ListaOficial,
    PropuestaProducto,
    Tienda,
    VersionListaOficial,
)
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

COLEGIO = uuid.UUID("44444444-4444-5444-8444-444444444444")
PDF_FALSO = b"%PDF-1.4 documento ficticio de Acudiente Ficticio"

H_C_06 = (
    "H-C-06: el router /v1/admin del catalogo nunca lee Authorization (routers/admin.py:44, sin dependencias)"
)


def _siembra(sesion) -> dict[str, uuid.UUID]:
    """Una version sin revisar con un renglon y una propuesta pendiente.

    Todo lo que las rutas protegidas necesitan para responder 2xx si nadie les
    pide credenciales: asi un 401/403 solo puede venir de una puerta de acceso,
    no de un recurso que falta.
    """
    cuaderno = Concepto(codigo="C001", nombre_canonico="cuaderno", categoria="Cuadernos")
    tienda = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    lista = ListaOficial(colegio_id=COLEGIO, grado="Cuarto", anio_lectivo=2026)
    sesion.add_all([cuaderno, tienda, lista])
    sesion.flush()
    version = VersionListaOficial(lista_id=lista.id, numero=1, vigente=True)
    sesion.add(version)
    sesion.flush()
    item = ItemListaOficial(
        version_id=version.id, orden=1, texto_original="2 cuadernos", cantidad=2, concepto_id=cuaderno.id
    )
    sesion.add(item)
    sesion.flush()
    propuesta = PropuestaProducto(
        concepto_id=cuaderno.id,
        texto_origen="cuaderno",
        tienda_id=tienda.id,
        referencia_externa="EX-1",
        nombre="Cuaderno ficticio",
        precio_centavos=550000,
        nivel_sugerido="confiable",
        estado="pendiente",
        version_lista_id=version.id,
        item_lista_id=item.id,
    )
    sesion.add(propuesta)
    sesion.flush()
    return {"version": version.id, "item": item.id, "propuesta": propuesta.id}


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as sesion:
        ids = await sesion.run_sync(lambda s: _siembra(s))
        await sesion.commit()

    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as http:
        http.ids = ids  # type: ignore[attr-defined]
        http.fabrica = fabrica  # type: ignore[attr-defined]
        yield http
    await engine.dispose()


async def _con_documento(cliente) -> str:
    """Importa una lista con su PDF de evidencia y devuelve el id de la version resultante."""
    cuerpo = {
        "colegio_id": str(COLEGIO),
        "grado": "Quinto",
        "anio_lectivo": 2026,
        "items": [{"texto_original": "lapices", "cantidad": 1}],
        "evidencia": {
            "documento_base64": base64.b64encode(PDF_FALSO).decode("ascii"),
            "percepcion_cruda": [{"pagina": 1, "crudo": "lapices"}],
        },
    }
    return (await cliente.post("/v1/admin/listas/importar", json=cuerpo)).json()["version_id"]


# (metodo, ruta con {version}/{item}/{propuesta}, cuerpo): las rutas de la consola de revision.
RUTAS_DE_STAFF = [
    ("GET", "/v1/admin/listas", None),
    ("GET", "/v1/admin/sugerencias", None),
    ("PATCH", "/v1/admin/listas/{version}/items/{item}", {"cantidad": 3}),
    ("POST", "/v1/admin/listas/{version}/items", {"texto_original": "borrador"}),
    ("DELETE", "/v1/admin/listas/{version}/items/{item}", None),
    ("DELETE", "/v1/admin/listas/{version}", None),
    ("PATCH", "/v1/admin/listas/{version}/colegio", {"direccion": "Calle Ficticia 1"}),
    ("POST", "/v1/admin/listas/{version}/cerrar", None),
    ("POST", "/v1/admin/propuestas/{propuesta}/rechazar", {"motivo": "no aplica"}),
    ("POST", "/v1/admin/listas/" + str(COLEGIO) + "/Cuarto/nueva-version?anio_lectivo=2026", None),
    ("GET", "/v1/admin/catalogo/propuestas", None),
    ("POST", "/v1/admin/catalogo/conceptos", {"nombre_canonico": "pegante", "categoria": "Arte"}),
]


@pytest.mark.xfail(strict=True, reason=H_C_06)
@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo"),
    RUTAS_DE_STAFF,
    ids=[f"{m} {r.split('/v1/admin')[1].split('?')[0]}" for m, r, _ in RUTAS_DE_STAFF],
)
async def test_sin_testigo_de_staff_las_rutas_de_revision_se_rechazan(cliente, metodo, ruta, cuerpo):
    """Sin cabecera `Authorization`, una ruta de la consola de revision responde 401 o 403.

    Es la misma convencion que `/v1/admin/acudientes` (identidad) y las vistas
    de equipo de inteligencia. Hoy el router atiende al anonimo: un 2xx.
    """
    ruta = ruta.format(
        version=cliente.ids["version"], item=cliente.ids["item"], propuesta=cliente.ids["propuesta"]
    )
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code in (401, 403)


@pytest.mark.xfail(strict=True, reason=H_C_06)
async def test_un_token_invalido_no_abre_la_consola_de_revision(cliente):
    """Un `Authorization: Bearer` que no corresponde a ninguna sesion es 401, igual que sin token."""
    respuesta = await cliente.get("/v1/admin/listas", headers={"Authorization": "Bearer token-invalido"})
    assert respuesta.status_code == 401


@pytest.mark.xfail(strict=True, reason=H_C_06)
async def test_el_documento_de_un_acudiente_no_se_sirve_al_anonimo(cliente):
    """El PDF original que subio un acudiente (puede traer nombres de menores) exige sesion de staff."""
    vid = await _con_documento(cliente)
    respuesta = await cliente.get(f"/v1/admin/listas/{vid}/documento")
    assert respuesta.status_code in (401, 403)
    assert respuesta.content != PDF_FALSO


@pytest.mark.xfail(strict=True, reason=H_C_06)
async def test_un_borrado_anonimo_no_destruye_la_version(cliente):
    """Ademas del codigo, el efecto: una peticion sin credencial no puede borrar la version de la cola."""
    version = cliente.ids["version"]
    await cliente.delete(f"/v1/admin/listas/{version}")
    async with cliente.fabrica() as sesion:
        assert await sesion.get(VersionListaOficial, version) is not None
