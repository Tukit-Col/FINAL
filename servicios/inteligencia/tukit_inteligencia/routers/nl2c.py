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

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from tukit_comun.http import ErrorDominio

from .. import api, nl2c, nl2c_kit, trabajos
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


class PeticionInterpretar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: str = Field(min_length=1, max_length=4000)


class PeticionProponer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: str = Field(min_length=1, max_length=4000)
    perfil: Literal["Ahorrador", "Fan", "A tu Medida", "Premium"]


class PeticionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    propuesta_id: str = Field(min_length=32, max_length=32, pattern="^[0-9a-f]{32}$")
    decision: Literal["aceptada", "rechazada", "editada"]
    tipo: Literal["restricciones", "cambio", "descarte"]


@router.post("/v1/nl2c/interpretar", summary="Lenguaje libre a restricciones (propuesta)")
async def interpretar(
    cuerpo: PeticionInterpretar, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    _exigir_activo()
    usuario = await _usuario_de_sesion(authorization) if _token_bearer(authorization) else None
    limpio = nl2c.sanitizar(cuerpo.texto)
    if not limpio.texto:
        raise ErrorDominio("texto_vacio", "Cuentanos que necesitas para el kit.", estado=422)
    try:
        personajes = await _personajes_surtidos()
    except RemotoCaido:
        personajes = []
    try:
        respuesta, ms = await nl2c.consultar_modelo(
            nl2c.SISTEMA_INTERPRETAR,
            nl2c.armar_usuario(limpio, contexto="Personajes disponibles: " + ", ".join(personajes)),
            [nl2c.DECLARACION_FIJAR, nl2c.DECLARACION_SIN_ACCION],
            nl2c.HERRAMIENTAS_INTERPRETAR,
        )
    except nl2c.AsistenteNoDisponible as error:
        nl2c.auditar("interpretar_sin_servicio", usuario=nl2c.huella_usuario(usuario), motivo=str(error))
        raise _sin_servicio(error) from error

    base = {
        "latencia_ms": ms,
        "tokens": {"entrada": respuesta.tokens_entrada, "salida": respuesta.tokens_salida},
    }
    fijar = next((c for c in respuesta.llamadas if c["name"] == "fijar_restricciones"), None)
    if fijar is None:
        razon = next(
            (
                c["args"].get("motivo")
                for c in respuesta.llamadas
                if c["name"] == "sin_accion" and isinstance(c["args"], dict)
            ),
            "ambiguo",
        )
        nl2c.auditar(
            "interpretar_sin_accion",
            usuario=nl2c.huella_usuario(usuario),
            huella=limpio.huella,
            motivo=razon,
            **base,
        )
        return {
            "estado": "sin_accion",
            "mensaje": "No pudimos convertir eso en preferencias del kit. "
            "Puedes llenar el formulario o contarnos de otra forma.",
            **base,
        }
    try:
        r, ajustes = nl2c.proyectar_R(fijar["args"], personajes)
    except nl2c.ArgumentosInvalidos as error:
        nl2c.auditar(
            "interpretar_argumentos_invalidos",
            usuario=nl2c.huella_usuario(usuario),
            huella=limpio.huella,
            motivo=str(error),
            **base,
        )
        return {
            "estado": "invalido",
            "mensaje": "No logramos entender bien tu pedido. Puedes llenar el formulario como siempre.",
            **base,
        }
    dijo_presupuesto = bool((fijar["args"].get("filtros_duros") or {}).get("presupuesto_max_cop"))
    propuesta_id = nl2c_kit.registrar_emision(usuario)
    nl2c.auditar(
        "interpretar_propuesta",
        propuesta_id=propuesta_id,
        usuario=nl2c.huella_usuario(usuario),
        huella=limpio.huella,
        redacciones=limpio.redacciones,
        r=r.model_dump(),
        ajustes=len(ajustes),
        **base,
    )
    return {
        "estado": "propuesta",
        "propuesta_id": propuesta_id,
        "r": r.model_dump(),
        "preferencias": nl2c.a_preferencias(r),
        "resumen": nl2c_kit.texto_resumen_R(r),
        "ajustes": ajustes,
        "ui": nl2c.construir_ui_empezar(r, dijo_presupuesto=dijo_presupuesto),
        **base,
    }


@router.post("/v1/kits/{trabajo_id}/asistente/proponer", summary="Pedido sobre un kit a propuestas de cambio")
async def proponer(
    trabajo_id: uuid.UUID, cuerpo: PeticionProponer, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    _exigir_activo()
    usuario = await _usuario_de_sesion(authorization)
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
    ctx = nl2c_kit.contexto_del_kit(kit)
    limpio = nl2c.sanitizar(cuerpo.texto)
    if not limpio.texto or not ctx.lineas:
        raise ErrorDominio("texto_vacio", "Cuentanos que quieres cambiar de tu kit.", estado=422)
    try:
        respuesta, ms = await nl2c.consultar_modelo(
            nl2c.SISTEMA_KIT,
            nl2c.armar_usuario(limpio, contexto=ctx.texto),
            nl2c.DECLARACIONES_KIT,
            nl2c.HERRAMIENTAS_KIT,
        )
    except nl2c.AsistenteNoDisponible as error:
        nl2c.auditar(
            "proponer_sin_servicio",
            usuario=nl2c.huella_usuario(usuario),
            trabajo=str(trabajo_id),
            motivo=str(error),
        )
        raise _sin_servicio(error) from error

    res = nl2c_kit.validar_llamadas_kit(respuesta.llamadas, ctx, kit, str(trabajo_id))
    propuesta_id = nl2c_kit.registrar_emision(usuario, str(trabajo_id))
    base = {
        "latencia_ms": ms,
        "tokens": {"entrada": respuesta.tokens_entrada, "salida": respuesta.tokens_salida},
    }
    nl2c.auditar(
        "proponer_propuesta",
        propuesta_id=propuesta_id,
        usuario=nl2c.huella_usuario(usuario),
        trabajo=str(trabajo_id),
        huella=limpio.huella,
        redacciones=limpio.redacciones,
        propuestas=[(p["tipo"], p["props"]["item_id"]) for p in res.propuestas],
        rechazadas=res.rechazadas,
        sin_accion=res.sin_accion,
        **base,
    )
    componentes = list(res.propuestas) + ([res.explicacion] if res.explicacion else [])
    if not componentes:
        return {
            "estado": "sin_accion",
            "mensaje": "No encontramos un cambio que hacer con eso. "
            "Prueba, por ejemplo: «mas barato en cuadernos».",
            **base,
        }
    return {
        "estado": "propuesta",
        "propuesta_id": propuesta_id,
        "ui": {"version": 1, "componentes": componentes},
        **base,
    }


@router.post("/v1/nl2c/decision", summary="El padre acepto o rechazo una propuesta", status_code=202)
async def decision(
    cuerpo: PeticionDecision, authorization: Annotated[str | None, Header()] = None
) -> dict[str, str]:
    _exigir_activo()
    usuario = await _usuario_de_sesion(authorization) if _token_bearer(authorization) else None
    emision = nl2c_kit.emision_de(cuerpo.propuesta_id)
    # Una decision solo puede citar una propuesta que este servidor emitio, al mismo portador.
    if emision is None or emision[0] != nl2c.huella_usuario(usuario):
        raise ErrorDominio("propuesta_desconocida", "Esa propuesta no existe.", estado=404)
    nl2c.auditar(
        "decision",
        propuesta_id=cuerpo.propuesta_id,
        usuario=nl2c.huella_usuario(usuario),
        decision=cuerpo.decision,
        tipo=cuerpo.tipo,
    )
    return {"estado": "registrada"}
