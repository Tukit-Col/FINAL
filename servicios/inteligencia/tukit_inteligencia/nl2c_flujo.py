"""Los dos planes fijos del asistente, sin HTTP.

Las rutas (routers/nl2c.py) y el banco de ensayos (ensayos/nl2c) llaman a estas
mismas funciones, de modo que lo que se mide es el codigo que se despliega.
Cada plan: sanear el texto -> una llamada al modelo con funciones de lista blanca
-> validar y proyectar en el servidor -> armar la spec de UI. Nada aqui escribe
en el kit ni en las preferencias.
"""

from __future__ import annotations

from typing import Any

from . import nl2c, nl2c_kit


class TextoVacio(Exception):
    """Despues de sanear no queda texto que interpretar."""


def _medidas(respuesta: nl2c.RespuestaModelo, ms: int) -> dict[str, Any]:
    return {
        "latencia_ms": ms,
        "tokens": {"entrada": respuesta.tokens_entrada, "salida": respuesta.tokens_salida},
    }


async def interpretar_texto(texto: str, personajes: list[str], usuario: Any = None) -> dict[str, Any]:
    """Texto libre -> `{estado: propuesta|sin_accion|invalido, ...}`.

    Lanza `TextoVacio` si el saneado lo deja vacio y `nl2c.AsistenteNoDisponible`
    si el modelo no responde; la ruta traduce ambos a su codigo HTTP.
    """
    limpio = nl2c.sanitizar(texto)
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


async def proponer_en_kit(
    texto: str, kit: dict[str, Any], usuario: Any, trabajo_id: str
) -> tuple[dict[str, Any], nl2c_kit.ResultadoPropuestas | None]:
    """Pedido sobre un kit -> (respuesta JSON, resultado de validacion).

    El resultado de validacion (con los codigos de rechazo) es para el banco de
    ensayos; la ruta solo devuelve la respuesta.
    """
    ctx = nl2c_kit.contexto_del_kit(kit)
    limpio = nl2c.sanitizar(texto)
    if not limpio.texto or not ctx.lineas:
        raise TextoVacio
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
    propuesta_id = nl2c_kit.registrar_emision(usuario, trabajo_id)
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
        **base,
    )
    componentes = list(res.propuestas) + ([res.explicacion] if res.explicacion else [])
    if not componentes:
        return (
            {
                "estado": "sin_accion",
                "mensaje": "No encontramos un cambio que hacer con eso. "
                "Prueba, por ejemplo: «mas barato en cuadernos».",
                **base,
            },
            res,
        )
    return (
        {
            "estado": "propuesta",
            "propuesta_id": propuesta_id,
            "ui": {"version": 1, "componentes": componentes},
            **base,
        },
        res,
    )
