"""El panel "Mis solicitudes" del acudiente: listas subidas + trabajos, unidas.

Dos capas se prueban aquí. La FUNCIÓN de dominio (`trabajos.mis_solicitudes`)
sobre el SQLite del conftest y un doble de catálogo en memoria: la unión de una
lista aprobada con su trabajo en una sola fila, la lista sin aprobar como
`recibida`, el trabajo sin lista como `trabajo`, el orden por fecha (que ejercita
la normalización naive/aware) y la degradación parcial cuando el catálogo cae. Y
la PUERTA HTTP (`GET /v1/mis-solicitudes`): 401 sin token o token inválido, 503
si identidad no responde (falla cerrada), y que el `usuario_id` que llega al
catálogo es SIEMPRE el de la sesión, nunca uno del navegador.

Con `ASGITransport`, sin uvicorn ni Postgres: se inyectan el motor, el doble de
identidad y el de catálogo por `app.state`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import insert
from tukit_inteligencia import trabajos
from tukit_inteligencia.api import app
from tukit_inteligencia.modelos import Base, EstadoTrabajo
from tukit_inteligencia.remoto import RemotoCaido

TRABAJO = Base.metadata.tables["trabajo_pipeline"]

COLEGIO = "22222222-2222-5222-8222-222222222222"
# Dos acudientes reales (UUID válidos): el token resuelve a uno de ellos.
PADRE = uuid.UUID("aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa")
OTRO_PADRE = uuid.UUID("bbbbbbbb-bbbb-5bbb-8bbb-bbbbbbbbbbbb")


@dataclass
class IdentidadFalsa:
    """Doble del puerto hacia identidad: token→usuario_id (UUID). Un token
    ausente vale como inválido (`None` => 401); `caida=True` lanza `RemotoCaido`
    para probar el fallo cerrado (503)."""

    usuario_por_token: dict[str, uuid.UUID] = field(default_factory=dict)
    caida: bool = False

    async def sesion(self, token: str) -> dict[str, Any] | None:
        if self.caida:
            raise RemotoCaido("identidad", "simulada")
        if token not in self.usuario_por_token:
            return None
        return {
            "usuario_id": str(self.usuario_por_token[token]),
            "correo": f"{token}@tukit.co",
            "nombre": token,
            "roles": [{"rol": "acudiente", "ambito": None}],
            "version_permisos": 1,
        }


@dataclass
class CatalogoListasFalso:
    """Doble del puerto hacia catálogo: `listas_por_contacto`, registrando el
    contacto pedido. `caida=True` lanza `RemotoCaido` (degradación parcial)."""

    por_contacto: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    caida: bool = False
    contactos_pedidos: list[str] = field(default_factory=list)

    async def listas_por_contacto(self, contacto_referencia: str) -> list[dict[str, Any]]:
        self.contactos_pedidos.append(contacto_referencia)
        if self.caida:
            raise RemotoCaido("catalogo", "simulada")
        return list(self.por_contacto.get(contacto_referencia, ()))


async def _sembrar_trabajo(
    motor,
    *,
    usuario_id: uuid.UUID,
    estado: str = EstadoTrabajo.PUBLICADO.value,
    origen: str = "colegio_grado",
    hijos: list[dict[str, Any]],
    creado_en: datetime | None = None,
) -> uuid.UUID:
    trabajo_id = uuid.uuid4()
    error = "prueba" if estado == EstadoTrabajo.FALLIDO.value else None
    valores: dict[str, Any] = {
        "id": trabajo_id,
        "usuario_id": usuario_id,
        "estado": estado,
        "origen": origen,
        "hijos": hijos,
        "error": error,
    }
    if creado_en is not None:
        valores["creado_en"] = creado_en
    async with motor.sesion() as db:
        conexion = await db.connection()
        await conexion.execute(insert(TRABAJO).values(**valores))
    return trabajo_id


def _lista(
    *,
    version_id: str | None,
    revisada: bool,
    grado: str = "Quinto",
    colegio_nombre: str | None = None,
    creada_en: str,
) -> dict[str, Any]:
    return {
        "version_id": version_id,
        "colegio_id": COLEGIO,
        "colegio_nombre": colegio_nombre,
        "grado": grado,
        "anio_lectivo": 2026,
        "revisada_en": creada_en if revisada else None,
        "creada_en": creada_en,
    }


# --------------------------------------------------------------------------
# La función de dominio
# --------------------------------------------------------------------------


async def test_lista_aprobada_y_su_trabajo_se_unen(motor):
    # Una lista aprobada y el trabajo que engendró (mismo version_id) salen como
    # UNA sola solicitud `aprobada`, no como dos filas.
    version_id = str(uuid.uuid4())
    trabajo_id = await _sembrar_trabajo(
        motor,
        usuario_id=PADRE,
        origen="lista_verificada",
        estado=EstadoTrabajo.PUBLICADO.value,
        hijos=[{"colegio_id": COLEGIO, "grado": "Quinto", "version_id": version_id}],
    )
    catalogo = CatalogoListasFalso(
        por_contacto={
            str(PADRE): [_lista(version_id=version_id, revisada=True, creada_en="2026-01-01T10:00:00+00:00")]
        }
    )

    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)

    assert resultado["listas_disponibles"] is True
    assert len(resultado["solicitudes"]) == 1
    solicitud = resultado["solicitudes"][0]
    assert solicitud["tipo"] == "aprobada"
    assert solicitud["trabajo_id"] == str(trabajo_id)
    assert solicitud["colegio_id"] == COLEGIO


async def test_lista_sin_aprobar_es_recibida(motor):
    catalogo = CatalogoListasFalso(
        por_contacto={
            str(PADRE): [
                _lista(
                    version_id=str(uuid.uuid4()),
                    revisada=False,
                    colegio_nombre="Colegio Nuevo",
                    creada_en="2026-01-01T10:00:00+00:00",
                )
            ]
        }
    )

    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)

    assert len(resultado["solicitudes"]) == 1
    solicitud = resultado["solicitudes"][0]
    assert solicitud["tipo"] == "recibida"
    assert solicitud["colegio_nombre"] == "Colegio Nuevo"
    assert "trabajo_id" not in solicitud


async def test_trabajo_sin_lista_es_trabajo(motor):
    trabajo_id = await _sembrar_trabajo(
        motor,
        usuario_id=PADRE,
        estado=EstadoTrabajo.ESPERA_REVISION.value,
        hijos=[{"colegio_id": COLEGIO, "grado": "Tercero"}],
    )
    catalogo = CatalogoListasFalso(por_contacto={})

    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)

    assert len(resultado["solicitudes"]) == 1
    solicitud = resultado["solicitudes"][0]
    assert solicitud["tipo"] == "trabajo"
    assert solicitud["trabajo_id"] == str(trabajo_id)
    assert solicitud["estado"] == EstadoTrabajo.ESPERA_REVISION.value
    assert solicitud["grado"] == "Tercero"


async def test_solo_devuelve_datos_del_portador(motor):
    # Un trabajo de OTRO padre no debe aparecer en las solicitudes del portador.
    await _sembrar_trabajo(motor, usuario_id=OTRO_PADRE, hijos=[{"colegio_id": COLEGIO, "grado": "Quinto"}])
    mio = await _sembrar_trabajo(motor, usuario_id=PADRE, hijos=[{"colegio_id": COLEGIO, "grado": "Quinto"}])
    catalogo = CatalogoListasFalso(por_contacto={})

    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)

    ids = {s.get("trabajo_id") for s in resultado["solicitudes"]}
    assert ids == {str(mio)}
    # Y el catálogo se consultó con el usuario_id del portador, jamás con otro.
    assert catalogo.contactos_pedidos == [str(PADRE)]


async def test_orden_mas_reciente_primero(motor):
    # Un trabajo naive (SQLite) y una lista con fecha ISO aware: ordenar mezclando
    # ambos no debe lanzar TypeError, y la más reciente va primero.
    viejo = datetime(2026, 1, 1, 8, 0, 0)  # naive, como vuelve de SQLite
    await _sembrar_trabajo(
        motor, usuario_id=PADRE, hijos=[{"colegio_id": COLEGIO, "grado": "Primero"}], creado_en=viejo
    )
    reciente = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    catalogo = CatalogoListasFalso(
        por_contacto={str(PADRE): [_lista(version_id=str(uuid.uuid4()), revisada=False, creada_en=reciente)]}
    )

    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)

    tipos = [s["tipo"] for s in resultado["solicitudes"]]
    assert tipos == ["recibida", "trabajo"]  # la lista reciente antes que el trabajo viejo


async def test_catalogo_caido_devuelve_trabajos_y_marca_listas_no_disponibles(motor):
    trabajo_id = await _sembrar_trabajo(
        motor, usuario_id=PADRE, hijos=[{"colegio_id": COLEGIO, "grado": "Quinto"}]
    )
    catalogo = CatalogoListasFalso(caida=True)

    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)

    assert resultado["listas_disponibles"] is False
    assert [s["trabajo_id"] for s in resultado["solicitudes"]] == [str(trabajo_id)]


# --------------------------------------------------------------------------
# La puerta HTTP
# --------------------------------------------------------------------------

RUTA = "/v1/mis-solicitudes"


@pytest.fixture()
async def cliente(motor):
    app.state.motor = motor
    app.state.identidad = IdentidadFalsa(usuario_por_token={"tok-padre": PADRE})
    app.state.catalogo = CatalogoListasFalso(por_contacto={})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    for attr in ("identidad", "catalogo"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)


async def test_sin_token_es_401(cliente):
    respuesta = await cliente.get(RUTA)
    assert respuesta.status_code == 401
    assert respuesta.json()["error"] == "sesion_invalida"


async def test_token_invalido_es_401(cliente):
    respuesta = await cliente.get(RUTA, headers={"Authorization": "Bearer no-existe"})
    assert respuesta.status_code == 401
    assert respuesta.json()["error"] == "sesion_invalida"


async def test_identidad_caida_falla_cerrada_503(motor):
    app.state.motor = motor
    app.state.identidad = IdentidadFalsa(caida=True)
    app.state.catalogo = CatalogoListasFalso(por_contacto={})
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            respuesta = await http.get(RUTA, headers={"Authorization": "Bearer tok-padre"})
        assert respuesta.status_code == 503
        assert respuesta.json()["error"] == "identidad_no_disponible"
    finally:
        for attr in ("identidad", "catalogo"):
            if hasattr(app.state, attr):
                delattr(app.state, attr)


async def test_portador_usa_el_usuario_de_la_sesion(motor):
    # Un trabajo del portador y otro de un tercero: la puerta solo devuelve el del
    # portador, y consulta al catálogo con SU usuario_id (el de la sesión).
    await _sembrar_trabajo(motor, usuario_id=OTRO_PADRE, hijos=[{"colegio_id": COLEGIO, "grado": "Quinto"}])
    mio = await _sembrar_trabajo(motor, usuario_id=PADRE, hijos=[{"colegio_id": COLEGIO, "grado": "Quinto"}])
    app.state.motor = motor
    app.state.identidad = IdentidadFalsa(usuario_por_token={"tok-padre": PADRE})
    catalogo = CatalogoListasFalso(por_contacto={})
    app.state.catalogo = catalogo
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            respuesta = await http.get(RUTA, headers={"Authorization": "Bearer tok-padre"})
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert [s["trabajo_id"] for s in cuerpo["solicitudes"]] == [str(mio)]
        assert catalogo.contactos_pedidos == [str(PADRE)]
    finally:
        for attr in ("identidad", "catalogo"):
            if hasattr(app.state, attr):
                delattr(app.state, attr)
