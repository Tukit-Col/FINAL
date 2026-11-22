from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from . import nl2c, nl2c_kit, nl2c_lote


class TextoVacio(Exception):
    pass


def _medidas(respuesta: nl2c.RespuestaModelo, ms: int) -> dict[str, Any]:
    return {
        "latencia_ms": ms,
        "tokens": {"entrada": respuesta.tokens_entrada, "salida": respuesta.tokens_salida},
    }


def _palabras_de(personajes: list[str] | set[str] | frozenset[str]) -> frozenset[str]:
    return frozenset(w for p in personajes for w in str(p).replace("-", " ").lower().split())


async def interpretar_texto(texto: str, personajes: list[str], usuario: Any = None) -> dict[str, Any]:
    limpio = nl2c.sanitizar(texto, conservar=_palabras_de(personajes))
    if not limpio.texto:
        raise TextoVacio
    try:
        respuesta, ms = await nl2c.consultar_modelo(
            nl2c.SISTEMA_INTERPRETAR,
            nl2c.armar_usuario(limpio, contexto="Personajes disponibles: " + ", ".join(personajes)),
            [nl2c.DECLARACION_FIJAR, nl2c.DECLARACION_SIN_ACCION],
            nl2c.HERRAMIENTAS_INTERPRETAR,
        )
    except nl2c.AsistenteNoDisponible as error:
        nl2c.auditar("interpretar_sin_servicio", usuario=nl2c.huella_usuario(usuario), motivo=str(error))
        raise

    base = _medidas(respuesta, ms)
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
        razon = razon if razon in nl2c.MOTIVOS_SIN_ACCION else "ambiguo"
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
        r, ajustes = nl2c.proyectar_R(fijar["args"], personajes, texto_base=limpio.texto)
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


OpcionesDe = Callable[[dict[str, Any]], Awaitable[list[dict[str, Any]]]]


async def proponer_en_kit(
    texto: str,
    kit: dict[str, Any],
    usuario: Any,
    trabajo_id: str,
    *,
    anterior: Any = None,
    opciones_de: OpcionesDe | None = None,
    personajes_por_hijo: dict[str, list[str]] | None = None,
) -> tuple[dict[str, Any], nl2c_kit.ResultadoPropuestas | None]:
    ctx = nl2c_kit.contexto_del_kit(kit, anterior)
    del_kit = {
        str(prod.get("personaje"))
        for linea in kit.get("lineas") or []
        for prod in [linea.get("producto_elegido") or {}, *(linea.get("alternativas") or [])]
        if isinstance(prod, dict) and prod.get("personaje")
    }
    pedidos = {p for lista in (personajes_por_hijo or {}).values() for p in lista}
    limpio = nl2c.sanitizar(texto, conservar=_palabras_de(del_kit | pedidos))
    if not limpio.texto or not ctx.lineas:
        raise TextoVacio
    if nl2c_lote.pide_ayuda(limpio.texto):
        nl2c.auditar(
            "proponer_ayuda",
            usuario=nl2c.huella_usuario(usuario),
            trabajo=trabajo_id,
            huella=limpio.huella,
            via="regla",
        )
        return nl2c_kit.respuesta_ayuda(ctx), None
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
            trabajo=trabajo_id,
            motivo=str(error),
        )
        raise

    res = nl2c_kit.validar_llamadas_kit(respuesta.llamadas, ctx, kit, trabajo_id)
    await nl2c_kit.completar_variar(res, ctx, trabajo_id, opciones_de, personajes_por_hijo)
    await nl2c_kit.completar_lote(res, ctx, trabajo_id, opciones_de)
    tipos = {
        nl2c_kit.TIPO_DE_COMPONENTE[p["tipo"]]
        for p in res.propuestas
        if p["tipo"] in nl2c_kit.TIPO_DE_COMPONENTE
    }
    propuesta_id = nl2c_kit.registrar_emision(usuario, trabajo_id, tipos)
    base = _medidas(respuesta, ms)
    nl2c.auditar(
        "proponer_propuesta",
        propuesta_id=propuesta_id,
        usuario=nl2c.huella_usuario(usuario),
        trabajo=trabajo_id,
        huella=limpio.huella,
        redacciones=limpio.redacciones,
        propuestas=[(p["tipo"], p["props"]["item_id"]) for p in res.propuestas],
        rechazadas=res.rechazadas,
        sin_accion=res.sin_accion,
        lote=res.lote,
        **base,
    )
    if res.ayuda and not res.propuestas and res.explicacion is None and res.lote is None:
        return {**nl2c_kit.respuesta_ayuda(ctx), **base}, res
    base_ui = ([res.resumen] if res.resumen else []) + list(res.propuestas)
    explicacion = [res.explicacion] if res.explicacion and len(base_ui) < nl2c.MAX_PROPUESTAS_LOTE + 1 else []
    componentes = base_ui + explicacion
    if not componentes:
        return (
            {
                "estado": "sin_accion",
                "mensaje": res.mensaje
                or "No encontré qué cambiar con eso. Pregúntame «¿qué puedes hacer?» y te muestro ejemplos.",
                **base,
            },
            res,
        )
    cuerpo: dict[str, Any] = {
        "estado": "propuesta",
        "propuesta_id": propuesta_id,
        "ui": {"version": 1, "componentes": componentes},
        **base,
    }
    if res.lote:
        cuerpo["contexto"] = {"accion": res.lote["accion"], "categoria": res.lote["categoria"]}
    return cuerpo, res
