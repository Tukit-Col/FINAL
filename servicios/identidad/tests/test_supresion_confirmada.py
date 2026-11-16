"""El cierre de la solicitud de supresion (Ley 1581, ADR 0048).

Cada servicio confirma con `supresion_confirmada` por `identidad.supresion`. La
solicitud sale de `propagando` solo cuando confirmaron los tres; una
confirmacion repetida no cambia nada, y una que llega con la solicitud ya
cerrada tampoco. Y `titular_suprimido`, como lo escribe `suprimir_titular`, sale
por el publicador comun.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from tukit_comun.bandeja import Resultado
from tukit_comun.bd import MotorServicio
from tukit_comun.mensajes import Evento
from tukit_comun.publicador import vaciar
from tukit_identidad.modelos import Base, SolicitudSupresion, Usuario
from tukit_identidad.repositorios import RepoIdentidad
from tukit_identidad.supresion import Cierre

TITULAR = uuid.uuid4()


async def _solicitud(motor: MotorServicio) -> uuid.UUID:
    async with motor.sesion() as db:
        db.add(Usuario(id=TITULAR, correo="ana@ejemplo.com", clave_hash="x"))
    async with motor.engine.begin() as conexion:
        return await RepoIdentidad(conexion).suprimir_titular(TITULAR, correo_nuevo="suprimido@tukit.invalid")


def _confirmacion(solicitud: uuid.UUID, servicio: str, id_: int = 1) -> Evento:
    return Evento(
        id=id_,
        origen=servicio,
        tipo="supresion_confirmada",
        agregado_tipo="solicitud_supresion",
        agregado_id=solicitud,
        carga={"solicitud_id": str(solicitud), "usuario_id": str(TITULAR), "servicio": servicio},
    )


async def _estado(motor: MotorServicio, solicitud: uuid.UUID) -> SolicitudSupresion:
    async with motor.sesion() as db:
        return await db.get(SolicitudSupresion, solicitud)


async def test_la_solicitud_se_cierra_cuando_confirman_los_tres(motor):
    solicitud = await _solicitud(motor)
    cierre = Cierre(motor)

    assert await cierre.manejar(_confirmacion(solicitud, "comercio")) is Resultado.HECHO
    assert await cierre.manejar(_confirmacion(solicitud, "operacion")) is Resultado.HECHO
    parcial = await _estado(motor, solicitud)
    assert parcial.estado == "propagando" and parcial.resuelto_en is None
    assert sorted(parcial.suscriptores_confirmados) == ["comercio", "operacion"]

    assert await cierre.manejar(_confirmacion(solicitud, "inteligencia")) is Resultado.HECHO
    cerrada = await _estado(motor, solicitud)
    assert cerrada.estado == "completada"
    assert cerrada.resuelto_en is not None


async def test_una_confirmacion_repetida_no_cierra_ni_duplica(motor):
    solicitud = await _solicitud(motor)
    cierre = Cierre(motor)

    for _ in range(3):
        await cierre.manejar(_confirmacion(solicitud, "comercio"))

    estado = await _estado(motor, solicitud)
    assert estado.estado == "propagando"
    assert estado.suscriptores_confirmados == ["comercio"]


async def test_una_confirmacion_tardia_no_reabre_la_solicitud(motor):
    solicitud = await _solicitud(motor)
    cierre = Cierre(motor)
    for servicio in ("comercio", "operacion", "inteligencia"):
        await cierre.manejar(_confirmacion(solicitud, servicio))
    resuelta = (await _estado(motor, solicitud)).resuelto_en

    assert await cierre.manejar(_confirmacion(solicitud, "comercio")) is Resultado.HECHO

    estado = await _estado(motor, solicitud)
    assert (estado.estado, estado.resuelto_en) == ("completada", resuelta)


async def test_omite_servicio_desconocido_solicitud_inexistente_o_carga_rota(motor):
    solicitud = await _solicitud(motor)
    cierre = Cierre(motor)

    assert await cierre.manejar(_confirmacion(solicitud, "catalogo")) is Resultado.OMITIR
    assert await cierre.manejar(_confirmacion(uuid.uuid4(), "comercio")) is Resultado.OMITIR
    roto = Evento(id=9, origen="comercio", tipo="supresion_confirmada", carga={"servicio": "comercio"})
    assert await cierre.manejar(roto) is Resultado.OMITIR
    assert (await _estado(motor, solicitud)).suscriptores_confirmados == []


async def test_titular_suprimido_sale_por_el_publicador_comun(motor):
    solicitud = await _solicitud(motor)

    class _Destino:
        publicados: list = []

        async def publicar(self, evento) -> None:
            self.publicados.append(evento)

    destino = _Destino()
    assert await vaciar(motor.engine, destino, origen="identidad") == 1
    [evento] = destino.publicados
    assert (evento.origen, evento.tipo, evento.agregado_id) == ("identidad", "titular_suprimido", solicitud)
    assert evento.carga["usuario_id"] == str(TITULAR)
    assert evento.carga["solicitud_id"] == str(solicitud)
    async with motor.engine.connect() as conexion:
        pendientes = (
            await conexion.execute(select(Base.metadata.tables["bandeja_salida"].c.publicado_en))
        ).scalar_one()
    assert pendientes is not None
