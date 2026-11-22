"""Puerto `Notificador` y sus adaptadores: wa-link y correo.

Decisiones:
- Dos adaptadores en esta version: wa-link (reactivo) y correo. Empujar por WhatsApp Business
  queda diferido; el puerto permite sumarlo sin tocar el dominio.
- El contacto (correo, celular) se resuelve contra Identidad en el momento de enviar y no se guarda:
  la notificacion referencia al destinatario por `usuario_id`.
- `NotificadorFalso` registra lo enviado sin salir a ninguna parte, para pruebas y desarrollo sin SMTP.
"""

from __future__ import annotations

import asyncio
import email.utils
import html
import logging
import os
import smtplib
import urllib.parse
import uuid
from dataclasses import dataclass, field, replace
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

_log = logging.getLogger("tukit.correo")


@dataclass(frozen=True)
class Contacto:
    usuario_id: str
    correo: str | None = None
    celular: str | None = None


@dataclass(frozen=True)
class Envio:
    canal: str
    exito: bool
    enlace: str | None = None
    detalle: str | None = None
    asunto: str | None = None
    destino_dominio: str | None = None
    omitido: bool = False


_DOMINIOS_NO_ENVIABLES = ("tukit.co", "example.com", "ejemplo.com")
_SUFIJOS_NO_ENVIABLES = (".test", ".invalid", ".local", ".example")


def destino_enviable(correo: str) -> bool:
    direccion = correo.strip().lower()
    permitidos = {c.strip().lower() for c in os.environ.get("TUKIT_CORREO_PERMITIDOS", "").split(",")}
    if direccion in permitidos:
        return True
    dominio = direccion.rsplit("@", 1)[-1]
    if dominio.endswith(_SUFIJOS_NO_ENVIABLES):
        return False
    return not any(dominio == d or dominio.endswith("." + d) for d in _DOMINIOS_NO_ENVIABLES)


class Notificador(Protocol):
    async def enviar(self, contacto: Contacto, plantilla: str, datos: dict[str, object]) -> Envio: ...


_PLANTILLAS = {
    "kits_publicados": (
        "Tu kit esta listo. Armamos la lista de {lugar}. "
        "Revisa los productos y elige cuando comprar: {enlace}"
    ),
    "pedido_pagado": (
        "Recibimos tu pago del pedido {pedido}. Ya empezamos a preparar tu kit; te avisamos cuando salga."
    ),
    "pedido_en_preparacion": "Estamos preparando el kit de tu pedido {pedido}. Te avisamos cuando salga.",
    "pedido_despachado": "Tu pedido {pedido} salió y va con {repartidor}.",
    "pedido_en_reparto": "Tu pedido {pedido} llega hoy.",
    "pedido_entregado": "Tu pedido {pedido} fue entregado. ¡Gracias por confiar en Tukit!",
    "incidencia": "Hubo una novedad con tu pedido {pedido}. Te contactaremos.",
    "pedido_cancelado": "Cancelamos tu pedido {pedido}.",
    "caso_respuesta": "Respondimos tu caso {caso}. Entra a Tukit para leer la respuesta.",
}

_TEXTOS_VARIANTE = {
    "pedido_en_preparacion:retoma": (
        "Retomamos tu pedido {pedido} y volvemos a preparar tu kit. Te avisamos cuando salga."
    ),
    "incidencia:cobro_tras_cancelacion": (
        "Recibimos un pago del pedido {pedido}, que ya estaba cancelado. Lo devolvemos a tu medio de pago."
    ),
    "pedido_cancelado:reembolso": "Cancelamos tu pedido {pedido} y te devolvemos el pago a tu medio de pago.",
    "pedido_cancelado:sin_cobro": "Cancelamos tu pedido {pedido}. No se hizo ningún cobro.",
    "kits_publicados:varias_listas": (
        "Tus kits estan listos. Armamos los kits de {lugar}. "
        "Revisa los productos y elige cuando comprar: {enlace}"
    ),
}


def _variante(plantilla: str, datos: dict[str, object]) -> str | None:
    if plantilla == "incidencia" and datos.get("motivo") == "pago_tras_cancelacion":
        return "cobro_tras_cancelacion"
    if plantilla == "pedido_en_preparacion" and datos.get("retoma"):
        return "retoma"
    if plantilla == "pedido_cancelado":
        return "reembolso" if datos.get("reembolso") else "sin_cobro"
    listas = datos.get("listas")
    if plantilla == "kits_publicados" and isinstance(listas, list) and len(listas) > 1:
        return "varias_listas"
    return None


def texto_de(plantilla: str, datos: dict[str, object]) -> str:
    variante = _variante(plantilla, datos)
    base = _TEXTOS_VARIANTE.get(f"{plantilla}:{variante}") if variante else None
    base = base or _PLANTILLAS.get(plantilla, "Tienes una novedad en Tukit.")
    try:
        return base.format(**datos)
    except (KeyError, IndexError):
        return base


_ASUNTOS = {
    "kits_publicados": "Tu kit esta listo",
    "pedido_pagado": "Recibimos tu pago",
    "pedido_en_preparacion": "Estamos preparando tu kit",
    "pedido_despachado": "Tu pedido salio",
    "pedido_en_reparto": "Tu pedido llega hoy",
    "pedido_entregado": "Tu pedido fue entregado",
    "incidencia": "Novedad con tu pedido",
    "pedido_cancelado": "Cancelamos tu pedido",
    "caso_respuesta": "Respondimos tu caso",
}


def asunto_de(plantilla: str, datos: dict[str, object] | None = None) -> str:
    asunto = _ASUNTOS.get(plantilla, "Novedad en Tukit")
    datos = datos or {}
    if datos.get("pedido"):
        return f"{asunto} · pedido {datos['pedido']}"
    if datos.get("caso"):
        return f"{asunto} · caso {datos['caso']}"
    return asunto


_AZUL = "#1f4fd8"
_TINTA = "#1b2540"
_APAGADO = "#4a5a85"
_FONDO = "#f3f5fb"
_SUAVE = "#eef2ff"


def _base_publica() -> str:
    base = (os.environ.get("TUKIT_PUBLIC_URL") or "").strip().rstrip("/")
    return base if base.lower().startswith(("http://", "https://")) else "http://localhost:3000"


def _contacto() -> str:
    return os.environ.get("TUKIT_SMTP_USER") or "ayuda@tukit.co"


def _url_logo() -> str | None:
    base = (os.environ.get("TUKIT_PUBLIC_URL") or "").strip().rstrip("/")
    if not base.lower().startswith(("http://", "https://")):
        return None
    return f"{base}/marca/icon-192.png"


_LOGO_ARCHIVO = Path(__file__).parent / "recursos" / "logo.png"


def _encabezado_html() -> str:
    logo = _url_logo()
    if logo is None and _LOGO_ARCHIVO.is_file():
        logo = "cid:logo-tukit"
    if logo is None:
        marca = (
            '<p style="margin:0;font-size:22px;letter-spacing:3px;color:#ffffff;font-weight:bold">TUKIT</p>'
        )
    else:
        marca = (
            f'<img src="{html.escape(logo, quote=True)}" alt="TUKIT" '
            'width="48" height="48" style="display:block;border:0;width:48px;height:48px;'
            'border-radius:12px">'
        )
    return (
        f'<tr><td bgcolor="{_AZUL}" style="background:{_AZUL};padding:22px 32px;'
        f'border-radius:16px 16px 0 0">{marca}</td></tr>'
    )


_FASES = ("Pago confirmado", "Preparando tu kit", "Despachado", "En reparto", "Entregado")


def _fases_html(actual: int) -> str:
    ultima = len(_FASES) - 1
    celdas = []
    for i, nombre in enumerate(_FASES):
        hecha = i <= actual
        color = _AZUL if hecha else "#d5dcef"
        marca = "&#10003; " if i < actual else ""
        peso = "bold" if i == actual else "normal"
        tinta = _TINTA if hecha else _APAGADO
        celdas.append(
            f'<td width="20%" valign="top" style="padding:0 {0 if i == ultima else 4}px 0 0">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td height="8" bgcolor="{color}" style="height:8px;line-height:8px;font-size:1px;'
            f'background:{color}">&nbsp;</td></tr></table>'
            f'<p style="margin:8px 0 0;font-size:11px;line-height:1.35;color:{tinta};'
            f'font-weight:{peso}">{marca}{nombre}</p></td>'
        )
    return (
        f'<p style="margin:0 0 10px;font-size:13px;color:{_APAGADO}">Ahora: '
        f'<b style="color:{_AZUL}">{_FASES[actual]}</b></p>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin:0 0 24px"><tr>{"".join(celdas)}</tr></table>'
    )


def _pie_html() -> str:
    base = _base_publica()
    contacto = html.escape(_contacto())
    estilo = f"margin:0 0 8px;font-size:12px;line-height:1.5;color:{_APAGADO}"
    enlace = f"color:{_APAGADO};text-decoration:underline"
    return (
        f'<tr><td style="padding:20px 32px 28px">'
        f'<p style="{estilo}">Recibes este aviso porque tienes una lista o un pedido en TUKIT. '
        "Es un correo de servicio sobre tu kit o tu pedido, no es publicidad.</p>"
        f'<p style="{estilo}">&iquest;No quieres m&aacute;s avisos? Responde este correo con la palabra '
        f'<b>BAJA</b> o escr&iacute;benos a <a href="mailto:{contacto}?subject=BAJA" style="{enlace}">'
        f"{contacto}</a> y dejamos de escribirte.</p>"
        f'<p style="{estilo}">Tratamos tus datos seg&uacute;n la Ley 1581 de 2012 (habeas data). '
        "Nunca ponemos el nombre ni el apodo de tus hijos en un correo. Puedes consultar, corregir "
        "o pedir que borremos tus datos escribi&eacute;ndonos.</p>"
        f'<p style="{estilo}"><a href="{base}/legal/privacidad" style="{enlace}">Pol&iacute;tica de '
        f"privacidad</a>"
        f' &middot; <a href="{base}/legal/terminos" style="{enlace}">T&eacute;rminos</a>'
        f' &middot; <a href="{base}/ayuda" style="{enlace}">Ayuda</a></p>'
        f'<p style="margin:0;font-size:12px;color:{_APAGADO}">TUKIT &middot; Bogot&aacute;, Colombia</p>'
        "</td></tr>"
    )


def _envolver_html(
    titulo: str,
    cuerpo: str,
    *,
    icono: str = "",
    previa: str = "",
    boton: tuple[str, str] | None = None,
    enlace_alterno: str | None = None,
) -> str:
    boton_html = ""
    if boton is not None:
        etiqueta, url = boton
        url_e = html.escape(url, quote=True)
        boton_html = (
            f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 20px"><tr>'
            f'<td bgcolor="{_AZUL}" style="background:{_AZUL};border-radius:10px">'
            f'<a href="{url_e}" style="display:inline-block;padding:15px 28px;color:#ffffff;'
            f'text-decoration:none;font-size:16px;font-weight:bold">{html.escape(etiqueta)}</a>'
            "</td></tr></table>"
            f'<p style="margin:0 0 4px;font-size:12px;line-height:1.5;color:{_APAGADO}">Si el bot&oacute;n '
            f"no abre, copia este enlace en tu navegador:<br>"
            f'<a href="{url_e}" style="color:{_AZUL};word-break:break-all">{url_e}</a></p>'
        )
    alterno = ""
    if enlace_alterno:
        alterno = f'<p style="margin:12px 0 0;font-size:13px;color:{_APAGADO}">{enlace_alterno}</p>'
    icono_html = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 16px"><tr>'
        f'<td width="56" height="56" align="center" bgcolor="{_SUAVE}" style="background:{_SUAVE};'
        f'border-radius:28px;font-size:28px;line-height:56px">{icono}</td></tr></table>'
        if icono
        else ""
    )
    previa_html = (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{_FONDO}">'
        f"{html.escape(previa)}</div>"
        if previa
        else ""
    )
    return (
        f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        f'<body style="margin:0;background:{_FONDO};font-family:Arial,Helvetica,sans-serif;color:{_TINTA}">'
        f"{previa_html}"
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{_FONDO}">'
        '<tr><td align="center" style="padding:28px 12px">'
        '<table role="presentation" width="560" cellpadding="0" cellspacing="0" '
        'style="width:100%;max-width:560px;background:#ffffff;border-radius:16px;'
        'box-shadow:0 2px 12px rgba(27,37,64,0.08)">'
        f"{_encabezado_html()}"
        f'<tr><td style="padding:32px 32px 8px">{icono_html}'
        f'<h1 style="margin:0 0 '
        f'12px;font-size:26px;line-height:1.25;color:{_TINTA}">{html.escape(titulo)}</h1>'
        f"{cuerpo}{boton_html}{alterno}</td></tr>"
        f'<tr><td style="padding:0 32px"><hr style="border:0;border-top:1px solid '
        f'#e3e8f5;margin:8px 0 0"></td></tr>'
        f"{_pie_html()}"
        "</table></td></tr></table></body></html>"
    )


def _detalle_html(filas: list[tuple[str, str]]) -> str:
    if not filas:
        return ""
    cuerpo = "".join(
        f'<tr><td style="padding:5px 0;font-size:13px;color:{_APAGADO}">{etiqueta}</td>'
        f'<td align="right" style="padding:5px '
        f'0;font-size:14px;font-weight:bold;color:{_TINTA}">{valor}</td></tr>'
        for etiqueta, valor in filas
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{_SUAVE}" '
        f'style="background:{_SUAVE};border-radius:12px;margin:0 0 20px"><tr><td style="padding:12px 18px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{cuerpo}</table>'
        "</td></tr></table>"
    )


_VISTAS: dict[str, dict[str, object]] = {
    "kits_publicados": {
        "icono": "&#127890;",
        "titulo": "Tu kit est&aacute; listo",
        "fase": None,
        "parrafo": "Armamos la lista de {lugar}. Revisa los productos y elige cu&aacute;ndo comprar.",
        "boton": "Ver mi kit",
        "ruta": "/dashboard",
        "usa_enlace": True,
        "previa": "Revisa tu kit y elige cuándo comprar.",
        "variantes": {
            "varias_listas": {
                "titulo": "Tus kits est&aacute;n listos",
                "parrafo": "Armamos los kits de {lugar}. Revisa los productos y elige cu&aacute;ndo comprar.",
            },
        },
    },
    "pedido_pagado": {
        "icono": "&#9989;",
        "titulo": "Recibimos tu pago",
        "fase": 0,
        "parrafo": "Tu pago lleg&oacute; bien. Ya empezamos a armar tu kit y te avisamos cuando salga.",
        "boton": "Ver mi pedido",
        "ruta": "/dashboard#pedidos",
        "usa_enlace": True,
        "previa": "Tu pago llegó. Ya armamos tu kit.",
    },
    "pedido_en_preparacion": {
        "icono": "&#9986;&#65039;",
        "titulo": "Estamos preparando tu kit",
        "fase": 1,
        "parrafo": "Estamos armando y revisando cada producto de tu kit. Te avisamos cuando salga.",
        "boton": "Ver mi pedido",
        "ruta": "/dashboard#pedidos",
        "usa_enlace": True,
        "previa": "Estamos armando tu kit.",
        "variantes": {
            "retoma": {
                "titulo": "Retomamos tu pedido",
                "parrafo": "Resolvimos la novedad y volvemos a preparar tu kit. Te avisamos cuando salga.",
            }
        },
    },
    "pedido_despachado": {
        "icono": "&#128230;",
        "titulo": "Tu pedido sali&oacute;",
        "fase": 2,
        "parrafo": "Tu pedido va en camino con <b>{repartidor}</b>.",
        "boton": "Seguir mi pedido",
        "ruta": "/dashboard#pedidos",
        "usa_enlace": True,
        "previa": "Tu pedido salió y va en camino.",
    },
    "pedido_en_reparto": {
        "icono": "&#128666;",
        "titulo": "Tu pedido llega hoy",
        "fase": 3,
        "parrafo": "Tu pedido est&aacute; en reparto y llega hoy. Ten a alguien en casa para recibirlo.",
        "boton": "Seguir mi pedido",
        "ruta": "/dashboard#pedidos",
        "usa_enlace": True,
        "previa": "Tu pedido llega hoy.",
    },
    "pedido_entregado": {
        "icono": "&#127881;",
        "titulo": "Tu pedido fue entregado",
        "fase": 4,
        "parrafo": (
            "Entregamos tu pedido. &iexcl;Gracias por confiar en TUKIT! Si algo no "
            "est&aacute; bien, cu&eacute;ntanos."
        ),
        "boton": "Ver mi pedido",
        "ruta": "/dashboard#pedidos",
        "usa_enlace": True,
        "previa": "Entregamos tu pedido. ¡Gracias!",
        "alterno": '&iquest;Algo no est&aacute; bien? <a href="{base}/dashboard#casos" style="color:'
        + _AZUL
        + '">Abre un caso</a>.',
    },
    "incidencia": {
        "icono": "&#9888;&#65039;",
        "titulo": "Novedad con tu pedido",
        "fase": None,
        "parrafo": "Hubo una novedad con tu pedido. Ya la estamos revisando y te vamos a contactar.",
        "boton": "Ver mi pedido",
        "ruta": "/dashboard#pedidos",
        "usa_enlace": True,
        "previa": "Hubo una novedad con tu pedido.",
        "alterno": 'Si necesitas ayuda ya, <a href="{base}/dashboard#casos" style="color:'
        + _AZUL
        + '">abre un caso</a>.',
        "variantes": {
            "cobro_tras_cancelacion": {
                "titulo": "Devolvemos un pago",
                "parrafo": (
                    "Recibimos un pago de un pedido que ya estaba cancelado. Lo devolvemos a "
                    "tu medio de pago; "
                    "el banco puede tardar unos d&iacute;as en reflejarlo."
                ),
            }
        },
    },
    "pedido_cancelado": {
        "icono": "&#10060;",
        "titulo": "Cancelamos tu pedido",
        "fase": None,
        "parrafo": "Cancelamos tu pedido.",
        "boton": "Ver mi pedido",
        "ruta": "/dashboard#pedidos",
        "usa_enlace": True,
        "previa": "Cancelamos tu pedido.",
        "alterno": '&iquest;Dudas? <a href="{base}/dashboard#casos" style="color:'
        + _AZUL
        + '">Abre un caso</a>.',
        "variantes": {
            "reembolso": {
                "parrafo": "Cancelamos tu pedido y te devolvemos el pago a tu medio de pago. "
                "El banco puede tardar unos d&iacute;as en reflejarlo.",
            },
            "sin_cobro": {"parrafo": "Cancelamos tu pedido. No se hizo ning&uacute;n cobro."},
        },
    },
    "caso_respuesta": {
        "icono": "&#128172;",
        "titulo": "Respondimos tu caso",
        "fase": None,
        "parrafo": "Ya hay una respuesta a tu caso. Entra a TUKIT para leerla.",
        "boton": "Leer la respuesta",
        "ruta": "/dashboard#casos",
        "usa_enlace": False,
        "previa": "Tu caso tiene respuesta.",
    },
}


def destino_de(plantilla: str, datos: dict[str, object]) -> str:
    base = _base_publica()
    vista = _VISTAS.get(plantilla, {})
    if vista.get("usa_enlace") and datos.get("enlace"):
        return str(datos["enlace"])
    return f"{base}{vista.get('ruta', '/dashboard')}"


def _cop(valor: object) -> str:
    try:
        return "$" + f"{int(valor):,}".replace(",", ".")  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return ""


def html_de(plantilla: str, datos: dict[str, object]) -> str | None:
    if plantilla not in _PLANTILLAS:
        return None
    vista = _VISTAS[plantilla]
    base = _base_publica()
    variante = (vista.get("variantes") or {}).get(_variante(plantilla, datos) or "", {})  # type: ignore[union-attr]

    def v(clave: str, por_omision: str = "") -> str:
        return html.escape(str(datos.get(clave) or por_omision))

    titulo = html.unescape(str(variante.get("titulo") or vista["titulo"]))
    parrafo = str(variante.get("parrafo") or vista["parrafo"]).format(
        lugar=v("lugar", "tu lista escolar"), repartidor=v("repartidor", "nuestro repartidor")
    )
    filas: list[tuple[str, str]] = []
    if plantilla == "kits_publicados":
        listas = [html.escape(str(li)) for li in (datos.get("listas") or ()) if str(li).strip()]  # type: ignore[union-attr]
        if len(listas) > 1:
            filas.append(("Listas", "<br>".join(listas)))
        else:
            filas.append(("Lista", v("lugar", "tu lista escolar")))
    elif plantilla == "caso_respuesta":
        if datos.get("caso"):
            filas.append(("Caso", v("caso")))
    else:
        if datos.get("pedido"):
            filas.append(("Pedido", v("pedido")))
        if plantilla == "pedido_pagado" and _cop(datos.get("total")):
            filas.append(("Total pagado", html.escape(_cop(datos.get("total")))))
        if plantilla == "pedido_despachado" and datos.get("repartidor"):
            filas.append(("Lo lleva", v("repartidor")))

    cuerpo = f'<p style="margin:0 0 20px;font-size:16px;line-height:1.55">{parrafo}</p>'
    if isinstance(vista["fase"], int):
        cuerpo += _fases_html(vista["fase"])
    cuerpo += _detalle_html(filas)

    alterno = str(vista.get("alterno", "")).replace("{base}", html.escape(base, quote=True)) or None
    return _envolver_html(
        titulo,
        cuerpo,
        icono=str(vista["icono"]),
        previa=str(vista["previa"]),
        boton=(str(vista["boton"]), destino_de(plantilla, datos)),
        enlace_alterno=alterno,
    )


def pie_texto() -> str:
    base = _base_publica()
    return (
        "\n\n--\n"
        "Recibes este aviso porque tienes una lista o un pedido en TUKIT. Es un correo de "
        "servicio, no es publicidad.\n"
        f"Para dejar de recibirlo, responde BAJA o escribe a {_contacto()}.\n"
        "Tratamos tus datos segun la Ley 1581 de 2012. Nunca ponemos el nombre de tus hijos en un correo.\n"
        f"Privacidad: {base}/legal/privacidad | Terminos: {base}/legal/terminos | Ayuda: {base}/ayuda\n"
        "TUKIT, Bogota, Colombia"
    )


def _buzon() -> Path | None:
    valor = os.environ.get("TUKIT_BUZON_DIR", ".ejecucion/buzon")
    return Path(valor) if valor else None


@dataclass
class WaLink:
    async def enviar(self, contacto: Contacto, plantilla: str, datos: dict[str, object]) -> Envio:
        if not contacto.celular:
            return Envio(canal="wa_link", exito=False, detalle="sin_celular")
        numero = "".join(c for c in contacto.celular if c.isdigit())
        mensaje = urllib.parse.quote(texto_de(plantilla, datos))
        enlace = f"https://wa.me/{numero}?text={mensaje}"
        return Envio(canal="wa_link", exito=True, enlace=enlace)


@dataclass
class Correo:
    remitente: str = ""

    def _smtp_host(self) -> str | None:
        return os.environ.get("TUKIT_SMTP_HOST") or None

    def _armar(self, destino: str, plantilla: str, datos: dict[str, object]) -> EmailMessage:
        desde = self.remitente or os.environ.get("TUKIT_SMTP_DESDE", "no-responder@tukit.co")
        if "@" not in desde:
            cuenta = os.environ.get("TUKIT_SMTP_USER") or "no-responder@tukit.co"
            desde = f"{desde.strip() or 'TUKIT'} <{cuenta}>"
        mensaje = EmailMessage()
        mensaje["From"] = desde
        mensaje["To"] = destino
        mensaje["Subject"] = asunto_de(plantilla, datos)
        mensaje["Date"] = email.utils.formatdate(localtime=True)
        mensaje["Message-ID"] = email.utils.make_msgid(domain=desde.rsplit("@", 1)[-1].strip(" >") or None)
        texto = texto_de(plantilla, datos)
        mensaje["List-Unsubscribe"] = f"<mailto:{_contacto()}?subject=BAJA>"
        destino = destino_de(plantilla, datos)
        if destino not in texto:
            texto = f"{texto}\n\nEntra aqui: {destino}"
        mensaje.set_content(texto + pie_texto())
        cuerpo_html = html_de(plantilla, datos)
        if cuerpo_html:
            mensaje.add_alternative(cuerpo_html, subtype="html")
            if "cid:logo-tukit" in cuerpo_html:
                mensaje.get_body(("html",)).add_related(
                    _LOGO_ARCHIVO.read_bytes(), "image", "png", cid="<logo-tukit>", disposition="inline"
                )
        return mensaje

    async def enviar(self, contacto: Contacto, plantilla: str, datos: dict[str, object]) -> Envio:
        if not contacto.correo:
            return Envio(canal="correo", exito=False, detalle="sin_correo")
        dominio = contacto.correo.rsplit("@", 1)[-1].strip().lower()
        asunto = asunto_de(plantilla, datos)
        if self._smtp_host() is not None and not destino_enviable(contacto.correo):
            return Envio(
                canal="correo",
                exito=False,
                detalle="destino_no_enviable",
                asunto=asunto,
                destino_dominio=dominio,
                omitido=True,
            )
        try:
            mensaje = self._armar(contacto.correo, plantilla, datos)
            host = self._smtp_host()
            if host is None:
                envio = self._enviar_consola(contacto.usuario_id, mensaje)
            else:
                envio = await asyncio.to_thread(self._enviar_smtp, host, mensaje)
        except Exception as error:  # noqa: BLE001 - un correo nunca tumba al repartidor
            _log.warning("correo no enviado (%s): %s", plantilla, type(error).__name__)
            envio = Envio(canal="correo", exito=False, detalle=f"error: {type(error).__name__}")
        return replace(envio, asunto=asunto, destino_dominio=dominio)

    def _enviar_consola(self, usuario_id: str, mensaje: EmailMessage) -> Envio:
        _log.info("[correo:consola] -> usuario %s: %s", usuario_id, mensaje["Subject"])
        print(f"[correo:consola] -> usuario {usuario_id}: {mensaje['Subject']}")
        carpeta = _buzon()
        if carpeta is not None:
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / f"{uuid.uuid4().hex}.eml").write_bytes(bytes(mensaje))
        return Envio(canal="correo", exito=True, detalle="consola")

    def _enviar_smtp(self, host: str, mensaje: EmailMessage) -> Envio:
        puerto = int(os.environ.get("TUKIT_SMTP_PORT", "587"))
        usuario = os.environ.get("TUKIT_SMTP_USER")
        clave = os.environ.get("TUKIT_SMTP_PASSWORD")
        try:
            with smtplib.SMTP(host, puerto, timeout=30) as servidor:
                servidor.starttls()
                if usuario and clave:
                    servidor.login(usuario, clave)
                servidor.send_message(mensaje)
            return Envio(canal="correo", exito=True, detalle="smtp")
        except OSError as error:
            return Envio(canal="correo", exito=False, detalle=f"smtp_error: {type(error).__name__}")


@dataclass
class NotificadorFalso:
    enviados: list[dict[str, object]] = field(default_factory=list)
    canal: str = "correo"

    async def enviar(self, contacto: Contacto, plantilla: str, datos: dict[str, object]) -> Envio:
        cuerpo = texto_de(plantilla, datos)
        self.enviados.append(
            {
                "usuario_id": contacto.usuario_id,
                "plantilla": plantilla,
                "canal": self.canal,
                "texto": cuerpo,
            }
        )
        return Envio(canal=self.canal, exito=True)


@dataclass
class NotificadorCompuesto:
    wa: Notificador = field(default_factory=WaLink)
    correo: Notificador = field(default_factory=Correo)

    async def enviar(self, contacto: Contacto, plantilla: str, datos: dict[str, object]) -> Envio:
        if contacto.celular:
            envio = await self.wa.enviar(contacto, plantilla, datos)
            if envio.exito:
                return envio
        return await self.correo.enviar(contacto, plantilla, datos)


def notificador_desde_entorno() -> Notificador:
    return NotificadorCompuesto()


__all__ = [
    "Notificador",
    "NotificadorCompuesto",
    "NotificadorFalso",
    "WaLink",
    "Correo",
    "Contacto",
    "Envio",
    "destino_enviable",
    "texto_de",
    "asunto_de",
    "html_de",
    "notificador_desde_entorno",
]
