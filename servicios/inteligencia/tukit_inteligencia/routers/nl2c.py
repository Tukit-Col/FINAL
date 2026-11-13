"""Las rutas del asistente NL2C. Detras de `TUKIT_ASISTENTE=1`.

Tres rutas, cada una con su plan fijo (nl2c.py):
- `POST /v1/nl2c/interpretar`: texto libre -> R + spec de UI. Sin datos del hogar.
- `POST /v1/kits/{trabajo_id}/asistente/proponer`: pedido sobre un kit -> propuestas.
  Exige que el portador sea el dueno del trabajo.
- `POST /v1/nl2c/decision`: deja en la bitacora si el padre acepto o rechazo.

Ninguna escribe en el kit ni en las preferencias: aplicar es una accion del padre
por los endpoints de siempre.
"""

from __future__ import annotations

import time
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from tukit_comun.http import ErrorDominio
from tukit_comun.red import ip_de_peticion

from .. import api, nl2c, nl2c_flujo, nl2c_kit, trabajos
from ..modelos import EstadoTrabajo
from ..remoto import RemotoCaido
from .inteligencia import _token_bearer, _usuario_de_sesion

router = APIRouter(tags=["asistente"])

ANCLAS = frozenset({"C001", "C009", "C011", "C086"})
_CACHE_PERSONAJES: tuple[float, list[str]] | None = None
_VIGENCIA_PERSONAJES = 300.0


async def _personajes_surtidos() -> list[str]:
    """Los personajes que el catalogo surte completos (las cuatro anclas), con cache corta."""
    global _CACHE_PERSONAJES
    ahora = time.monotonic()
    if _CACHE_PERSONAJES and ahora - _CACHE_PERSONAJES[0] < _VIGENCIA_PERSONAJES:
        return _CACHE_PERSONAJES[1]
    cuerpo = await api._catalogo()._pedir("GET", "/v1/catalogo/personajes")
    nombres = [
        str(p["nombre"])
        for p in sorted(cuerpo.get("personajes") or [], key=lambda p: -int(p.get("productos") or 0))
        if set(p.get("conceptos") or []) >= ANCLAS
    ][: nl2c.MAX_PERSONAJES_CATALOGO]
    _CACHE_PERSONAJES = (ahora, nombres)
    return nombres


def _exigir_activo() -> None:
    if not nl2c.activo():
        raise ErrorDominio("asistente_desactivado", "El asistente no esta disponible.", estado=404)


def _sin_servicio(error: Exception) -> ErrorDominio:
    # 503 con el mensaje que la web usa para caer al formulario clasico.
    return ErrorDominio(
        "asistente_no_disponible",
        "El asistente no esta disponible ahora. Puedes llenar el formulario como siempre.",
        estado=503,
    )


def _admitir(clave: str) -> None:
    """Cupo por portador antes de gastar una llamada al modelo (429)."""
    try:
        nl2c.LIMITADOR.admitir(clave)
    except nl2c.LimiteExcedido as error:
        nl2c.auditar("limite_excedido", clave=clave[:12], motivo=error.motivo)
        raise ErrorDominio(
            "asistente_limite",
            "Has usado el asistente muchas veces seguidas. Espera un momento o usa el formulario.",
            estado=429,
        ) from error


def _clave_de(usuario: uuid.UUID | None, peticion: Request) -> str:
    # Detras del gateway y de la web la conexion es de ellos: la IP del padre viene en
    # `X-Forwarded-For`, y solo se cree si la conexion es de un proxy de confianza
    # (`TUKIT_PROXIES_CONFIANZA`, la misma regla que el limite de la puerta).
    conexion = peticion.client.host if peticion.client else None
    return nl2c.huella_usuario(usuario) or "anon:" + ip_de_peticion(
        conexion, peticion.headers.getlist("x-forwarded-for")
    )


def _contar_tokens(clave: str, respuesta: dict[str, Any]) -> None:
    uso = respuesta.get("tokens") or {}
    nl2c.LIMITADOR.registrar_tokens(clave, int(uso.get("entrada") or 0) + int(uso.get("salida") or 0))


class PeticionInterpretar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: str = Field(min_length=1, max_length=4000)


class PedidoAnterior(BaseModel):
    """El ultimo pedido por categoria, para "y en colores tambien". Solo dos palabras acotadas:
    ni el texto del padre ni nada del hogar viaja de un turno al siguiente."""

    model_config = ConfigDict(extra="forbid")
    accion: Literal["mas_barato", "mejor_calidad", "variar"]
    categoria: str = Field(min_length=3, max_length=24, pattern="^[a-zñáéíóúü]+$")


class PeticionProponer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: str = Field(min_length=1, max_length=4000)
    perfil: Literal["Ahorrador", "Fan", "A tu Medida", "Premium"]
    anterior: PedidoAnterior | None = None


class PeticionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    propuesta_id: str = Field(min_length=32, max_length=32, pattern="^[0-9a-f]{32}$")
    decision: Literal["aceptada", "rechazada", "editada"]
    tipo: Literal["restricciones", "cambio", "descarte"]


@router.get("/v1/nl2c/estado", summary="Si el asistente esta encendido en este entorno")
async def estado() -> dict[str, Any]:
    """Para que la web distinga "apagado" de "caido" sin gastar una llamada al modelo.
    No revela claves: solo si la bandera esta en 1 y si hay clave del modelo (si/no)."""
    import os

    return {"activo": nl2c.activo(), "modelo_configurado": bool(os.environ.get("GEMINI_API_KEY", "").strip())}


@router.post("/v1/nl2c/interpretar", summary="Lenguaje libre a restricciones (propuesta)")
async def interpretar(
    cuerpo: PeticionInterpretar, peticion: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    _exigir_activo()
    usuario = await _usuario_de_sesion(authorization) if _token_bearer(authorization) else None
    clave = _clave_de(usuario, peticion)
    _admitir(clave)
    try:
        personajes = await _personajes_surtidos()
    except RemotoCaido:
        personajes = []
    try:
        respuesta = await nl2c_flujo.interpretar_texto(cuerpo.texto, personajes, usuario)
        _contar_tokens(clave, respuesta)
        return respuesta
    except nl2c_flujo.TextoVacio:
        raise ErrorDominio("texto_vacio", "Cuentanos que necesitas para el kit.", estado=422) from None
    except nl2c.AsistenteNoDisponible as error:
        raise _sin_servicio(error) from error


@router.post("/v1/kits/{trabajo_id}/asistente/proponer", summary="Pedido sobre un kit a propuestas de cambio")
async def proponer(
    trabajo_id: uuid.UUID,
    cuerpo: PeticionProponer,
    peticion: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _exigir_activo()
    usuario = await _usuario_de_sesion(authorization)
    clave = _clave_de(usuario, peticion)
    async with api.app.state.motor.engine.begin() as conexion:
        fila = (
            await conexion.execute(
                select(trabajos.TRABAJO.c.usuario_id, trabajos.TRABAJO.c.estado).where(
                    trabajos.TRABAJO.c.id == trabajo_id
                )
            )
        ).one_or_none()
    # Mismo mensaje para "no existe" y "es de otro": no se confirma que un id ajeno existe.
    if fila is None or fila.usuario_id != usuario:
        nl2c.auditar("proponer_denegado", usuario=nl2c.huella_usuario(usuario), trabajo=str(trabajo_id))
        raise ErrorDominio("kit_no_encontrado", "No encontramos ese kit en tu cuenta.", estado=404)
    if fila.estado != EstadoTrabajo.PUBLICADO.value:
        raise ErrorDominio("kit_no_publicado", "Tu kit todavia no esta listo para cambios.", estado=409)

    vista = await trabajos.ver(api.app.state.motor, trabajo_id, catalogo=api._catalogo())
    kit = next((k for k in vista["kits"] if k["perfil"] == cuerpo.perfil), None)
    if kit is None:
        raise ErrorDominio("kit_no_encontrado", "No encontramos ese kit en tu cuenta.", estado=404)

    async def opciones_de(linea: dict[str, Any]) -> list[dict[str, Any]]:
        # Las mismas opciones que el carrusel de LineaDeKit (`GET .../opciones`), de un trabajo
        # que ya verificamos que es del portador; los filtros del trabajo se aplican ahi.
        cuerpo_opc = await trabajos.opciones_de_una_linea(
            api.app.state.motor, trabajo_id, linea, catalogo=api._catalogo()
        )
        return list(cuerpo_opc.get("opciones") or [])

    _admitir(clave)
    try:
        respuesta, _ = await nl2c_flujo.proponer_en_kit(
            cuerpo.texto,
            kit,
            usuario,
            str(trabajo_id),
            anterior=cuerpo.anterior.model_dump() if cuerpo.anterior else None,
            opciones_de=opciones_de,
            personajes_por_hijo=vista.get("personajes_por_hijo") or {},
        )
    except nl2c_flujo.TextoVacio:
        raise ErrorDominio("texto_vacio", "Cuentanos que quieres cambiar de tu kit.", estado=422) from None
    except nl2c.AsistenteNoDisponible as error:
        raise _sin_servicio(error) from error
    _contar_tokens(clave, respuesta)
    return respuesta


@router.post("/v1/nl2c/decision", summary="El padre acepto o rechazo una propuesta", status_code=202)
async def decision(
    cuerpo: PeticionDecision, authorization: Annotated[str | None, Header()] = None
) -> dict[str, str]:
    _exigir_activo()
    usuario = await _usuario_de_sesion(authorization) if _token_bearer(authorization) else None
    emision = nl2c_kit.emision_de(cuerpo.propuesta_id, usuario)
    # Una decision solo puede citar una propuesta que este servidor emitio, al mismo portador,
    # y con un tipo que esa propuesta traia: la bitacora no puede decir "descarte" de un cambio.
    if emision is None:
        raise ErrorDominio("propuesta_desconocida", "Esa propuesta no existe.", estado=404)
    if cuerpo.tipo not in emision.tipos:
        raise ErrorDominio("decision_no_coincide", "Esa decision no corresponde a la propuesta.", estado=422)
    nl2c.auditar(
        "decision",
        propuesta_id=cuerpo.propuesta_id,
        usuario=nl2c.huella_usuario(usuario),
        decision=cuerpo.decision,
        tipo=cuerpo.tipo,
    )
    return {"estado": "registrada"}
