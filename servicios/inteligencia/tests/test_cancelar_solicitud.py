"""El acudiente cancela una solicitud (ADR 0031).

Un trabajo cancelado queda en `cancelado` (terminal) y deja de salir en "Mis
solicitudes". No se cancela un kit que ya se compro, ni uno con un pago
pendiente (primero se cancela el pedido), ni uno que el pipeline esta armando.
Una lista subida se desvincula del acudiente en el Catalogo, sin borrarla: sigue
siendo una lista del colegio.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from test_mis_solicitudes import COLEGIO, OTRO_PADRE, PADRE, IdentidadFalsa, _lista, _sembrar_trabajo
from tukit_inteligencia import trabajos
from tukit_inteligencia.api import app
from tukit_inteligencia.modelos import EstadoTrabajo


@dataclass
class CatalogoFalso:
    por_contacto: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    retiros: list[dict[str, Any]] = field(default_factory=list)

    async def listas_por_contacto(self, contacto_referencia: str) -> list[dict[str, Any]]:
        return list(self.por_contacto.get(contacto_referencia, ()))

    async def retirar_de_contacto(
        self, contacto_referencia: str, *, tarea_id: str | None = None, version_id: str | None = None
    ) -> int:
        self.retiros.append({"contacto": contacto_referencia, "tarea_id": tarea_id, "version_id": version_id})
        return 1


@dataclass
class ComercioFalso:
    pedidos: list[dict[str, Any]] = field(default_factory=list)

    async def pedidos_de(self, token: str) -> list[dict[str, Any]]:
        # Comercio resuelve el token a su dueno; aqui el token ES el usuario_id.
        return [p for p in self.pedidos if p.get("usuario_id", str(PADRE)) == token]


HIJOS = [{"colegio_id": COLEGIO, "grado": "Quinto"}]


async def _cancelar(motor, trabajo_id, *, comercio=None, catalogo=None, usuario_id=PADRE):
    return await trabajos.cancelar_solicitud(
        motor,
        trabajo_id,
        usuario_id=usuario_id,
        token=str(usuario_id),
        comercio=comercio or ComercioFalso(),
        catalogo=catalogo or CatalogoFalso(),
    )


async def test_cancelar_deja_el_trabajo_cancelado_y_fuera_de_mis_solicitudes(motor):
    trabajo_id = await _sembrar_trabajo(motor, usuario_id=PADRE, hijos=HIJOS)
    await _cancelar(motor, trabajo_id)

    vista = await trabajos.ver(motor, trabajo_id, incluir_kits=True)
    assert vista["estado"] == EstadoTrabajo.CANCELADO.value
    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=CatalogoFalso())
    assert resultado["solicitudes"] == []


async def test_un_kit_comprado_no_se_cancela(motor):
    trabajo_id = await _sembrar_trabajo(motor, usuario_id=PADRE, hijos=HIJOS)
    comercio = ComercioFalso(pedidos=[{"pedido_id": "p1", "trabajo_id": str(trabajo_id), "estado": "pagado"}])
    with pytest.raises(trabajos.SolicitudNoCancelable) as error:
        await _cancelar(motor, trabajo_id, comercio=comercio)
    assert error.value.codigo == "kit_comprado"


async def test_con_un_pago_pendiente_primero_se_cancela_el_pedido(motor):
    trabajo_id = await _sembrar_trabajo(motor, usuario_id=PADRE, hijos=HIJOS)
    comercio = ComercioFalso(
        pedidos=[{"pedido_id": "p1", "trabajo_id": str(trabajo_id), "estado": "pendiente_pago"}]
    )
    with pytest.raises(trabajos.SolicitudNoCancelable) as error:
        await _cancelar(motor, trabajo_id, comercio=comercio)
    assert error.value.codigo == "pedido_pendiente"


async def test_un_pedido_cancelado_no_impide_cancelar(motor):
    trabajo_id = await _sembrar_trabajo(motor, usuario_id=PADRE, hijos=HIJOS)
    comercio = ComercioFalso(
        pedidos=[{"pedido_id": "p1", "trabajo_id": str(trabajo_id), "estado": "cancelado"}]
    )
    await _cancelar(motor, trabajo_id, comercio=comercio)
    assert (await trabajos.ver(motor, trabajo_id))["estado"] == EstadoTrabajo.CANCELADO.value


async def test_la_solicitud_de_otro_no_se_cancela(motor):
    trabajo_id = await _sembrar_trabajo(motor, usuario_id=OTRO_PADRE, hijos=HIJOS)
    with pytest.raises(trabajos.SolicitudNoCancelable) as error:
        await _cancelar(motor, trabajo_id)
    assert error.value.codigo == "solicitud_ajena"
    assert error.value.estado == 403


async def test_mientras_se_arma_no_se_cancela(motor):
    trabajo_id = await _sembrar_trabajo(
        motor, usuario_id=PADRE, hijos=HIJOS, estado=EstadoTrabajo.PROCESANDO.value
    )
    with pytest.raises(trabajos.SolicitudNoCancelable) as error:
        await _cancelar(motor, trabajo_id)
    assert error.value.codigo == "en_proceso"


async def test_cancelar_dos_veces_no_falla(motor):
    trabajo_id = await _sembrar_trabajo(motor, usuario_id=PADRE, hijos=HIJOS)
    await _cancelar(motor, trabajo_id)
    await _cancelar(motor, trabajo_id)


async def test_el_trabajo_de_una_lista_subida_tambien_la_desvincula(motor):
    """Si no, la lista volveria a salir en "Mis solicitudes" como recibida."""
    version_id = str(uuid.uuid4())
    trabajo_id = await _sembrar_trabajo(
        motor,
        usuario_id=PADRE,
        origen="lista_verificada",
        hijos=[{**HIJOS[0], "version_id": version_id}],
    )
    catalogo = CatalogoFalso()
    await _cancelar(motor, trabajo_id, catalogo=catalogo)
    assert catalogo.retiros == [{"contacto": str(PADRE), "tarea_id": None, "version_id": version_id}]


async def test_cancelar_una_lista_recibida_la_desvincula_en_el_catalogo(motor):
    catalogo = CatalogoFalso()
    tarea_id = str(uuid.uuid4())
    await trabajos.cancelar_lista_subida(PADRE, tarea_id, catalogo=catalogo)
    assert catalogo.retiros == [{"contacto": str(PADRE), "tarea_id": tarea_id, "version_id": None}]


async def test_la_lista_recibida_trae_su_tarea_para_cancelarla(motor):
    lista = {
        **_lista(version_id=None, revisada=False, creada_en="2026-01-01T10:00:00+00:00"),
        "tarea_id": "t-1",
    }
    catalogo = CatalogoFalso(por_contacto={str(PADRE): [lista]})
    resultado = await trabajos.mis_solicitudes(motor, PADRE, catalogo=catalogo)
    assert resultado["solicitudes"][0]["tarea_id"] == "t-1"


# --------------------------------------------------------------------------
# La puerta HTTP
# --------------------------------------------------------------------------


@pytest.fixture()
async def cliente(motor):
    app.state.motor = motor
    app.state.identidad = IdentidadFalsa(usuario_por_token={"tok-padre": PADRE})
    app.state.catalogo = CatalogoFalso()
    app.state.comercio = ComercioFalso()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    for attr in ("identidad", "catalogo", "comercio"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)


async def test_cancelar_exige_sesion(cliente, motor):
    trabajo_id = await _sembrar_trabajo(motor, usuario_id=PADRE, hijos=HIJOS)
    respuesta = await cliente.post(f"/v1/trabajos/{trabajo_id}/cancelar")
    assert respuesta.status_code == 401


async def test_cancelar_con_sesion(cliente, motor):
    trabajo_id = await _sembrar_trabajo(motor, usuario_id=PADRE, hijos=HIJOS)
    respuesta = await cliente.post(
        f"/v1/trabajos/{trabajo_id}/cancelar", headers={"Authorization": "Bearer tok-padre"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "cancelado"


async def test_cancelar_lista_con_sesion(cliente):
    respuesta = await cliente.post(
        f"/v1/mis-solicitudes/listas/{uuid.uuid4()}/cancelar", headers={"Authorization": "Bearer tok-padre"}
    )
    assert respuesta.status_code == 200
    assert app.state.catalogo.retiros[0]["contacto"] == str(PADRE)
