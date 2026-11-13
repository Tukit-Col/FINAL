"""El puerto `Notificador` (FU-10) y sus adaptadores: wa-link y correo.

El §10 del contrato lo fija: un puerto con dos adaptadores en v1, wa-link
(FU-11, reactiva) y correo (FU-02). Empujar por WhatsApp Business (proactivo)
esta diferido a v2+ por decision del SRS, no por omision; el puerto existe para
que la Cloud API entre despues sin tocar el dominio.

La regla dura, y por eso vive aqui: el contacto (correo, celular) se resuelve
contra Identidad EN EL MOMENTO de enviar y NO se guarda. La notificacion en la
base referencia al destinatario por `usuario_id`; el dato de contacto entra en
esta capa, se usa para el envio y se descarta. Es la deuda que el manifiesto
documenta de `operacion.notificacion`.

`NotificadorFalso` registra lo enviado sin salir a ninguna parte, para las
pruebas y el desarrollo sin SMTP.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import smtplib
import urllib.parse
import uuid
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

_log = logging.getLogger("tukit.correo")


@dataclass(frozen=True)
class Contacto:
    """Lo que Identidad devuelve para poder entregar. Efimero: no se persiste."""

    usuario_id: str
    correo: str | None = None
    celular: str | None = None


@dataclass(frozen=True)
class Envio:
    """El resultado de un envio, para que el repartidor lo registre."""

    canal: str
    exito: bool
    # Para wa-link, el enlace generado; para correo, None. Nunca el contacto.
    enlace: str | None = None
    detalle: str | None = None


class Notificador(Protocol):
    """El puerto. El repartidor depende de esto, no de SMTP ni de wa.me."""

    async def enviar(self, contacto: Contacto, plantilla: str, datos: dict[str, object]) -> Envio: ...


# ---------------------------------------------------------------------------
# Plantillas: texto por clave. No llevan dato de contacto, solo variables de
# negocio (el turno, el numero de pedido). El contenido de la notificacion
# guardada tampoco los lleva.
# ---------------------------------------------------------------------------

_PLANTILLAS = {
    # Sin nombre ni apodo de menores (Ley 1581): solo colegio y grado, que salen
    # de la lista oficial y no identifican a nadie.
    "kits_publicados": (
        "Tu kit esta listo. Armamos la lista de {lugar}. "
        "Revisa los productos y elige cuando comprar: {enlace}"
    ),
    "pedido_pagado": "Recibimos tu pago del pedido {pedido}. Turno {turno}. Te avisamos cuando salga.",
    "incidencia": "Hubo una novedad con tu pedido {pedido}. Turno {turno}. Te contactaremos.",
    "pedido_despachado": "Tu pedido {pedido} salió y va con {repartidor}.",
    "pedido_en_reparto": "Tu pedido {pedido} llega hoy.",
    "pedido_entregado": "Tu pedido {pedido} fue entregado. ¡Gracias por confiar en Tukit!",
    "caso_respuesta": "Respondimos tu caso {caso}. Entra a Tukit para leer la respuesta.",
}


def texto_de(plantilla: str, datos: dict[str, object]) -> str:
    """Rellena la plantilla con los datos. Una plantilla sin registrar cae a un
    texto generico, para no reventar el envio por una clave nueva."""
    base = _PLANTILLAS.get(plantilla, "Tienes una novedad en Tukit. Turno {turno}.")
    try:
        return base.format(**datos)
    except (KeyError, IndexError):
        return base


_ASUNTOS = {
    "kits_publicados": "Tu kit esta listo",
    "pedido_pagado": "Recibimos tu pago",
    "incidencia": "Novedad con tu pedido",
    "pedido_despachado": "Tu pedido salio",
    "pedido_en_reparto": "Tu pedido llega hoy",
    "pedido_entregado": "Tu pedido fue entregado",
    "caso_respuesta": "Respondimos tu caso",
}


def asunto_de(plantilla: str) -> str:
    """El asunto del correo. Fijo por plantilla: nunca lleva datos del menor."""
    return _ASUNTOS.get(plantilla, "Novedad en Tukit")


def html_de(plantilla: str, datos: dict[str, object]) -> str | None:
    """El cuerpo HTML sobrio de las plantillas que lo tienen; `None` si solo texto.

    Estilos en linea y sin imagenes remotas: los clientes de correo no cargan CSS
    externo y un pixel de seguimiento no nos corresponde. Todo valor se escapa."""
    if plantilla != "kits_publicados":
        return None
    lugar = html.escape(str(datos.get("lugar", "tu lista escolar")))
    enlace = html.escape(str(datos.get("enlace", "")), quote=True)
    return (
        '<!doctype html><html lang="es"><body style="margin:0;background:#f4f6fb;'
        'font-family:Arial,Helvetica,sans-serif;color:#1b2540">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" '
        'style="padding:32px 16px"><table role="presentation" width="560" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;background:#ffffff;border-radius:12px;padding:32px">'
        '<tr><td><p style="margin:0 0 8px;font-size:14px;color:#4a5a85;font-weight:bold">TUKIT</p>'
        '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25">Tu kit esta listo</h1>'
        f'<p style="margin:0 0 24px;font-size:16px;line-height:1.5">Armamos la lista de {lugar}. '
        "Revisa los productos y elige cuando comprar.</p>"
        f'<p style="margin:0 0 24px"><a href="{enlace}" style="display:inline-block;background:#1f4fd8;'
        "color:#ffffff;text-decoration:none;padding:14px 24px;border-radius:8px;font-size:16px;"
        'font-weight:bold">Ver mi kit</a></p>'
        f'<p style="margin:0;font-size:13px;color:#4a5a85;line-height:1.5">Si el boton no abre, copia este '
        f"enlace en tu navegador: {enlace}</p></td></tr></table></td></tr></table></body></html>"
    )


def _buzon() -> Path | None:
    """La carpeta donde el modo consola deja el .eml. `TUKIT_BUZON_DIR` la cambia;
    vacia la apaga. Por omision `.ejecucion/buzon` (ignorada por git)."""
    valor = os.environ.get("TUKIT_BUZON_DIR", ".ejecucion/buzon")
    return Path(valor) if valor else None


@dataclass
class WaLink:
    """wa-link (FU-11): construye `https://wa.me/<numero>?text=<mensaje>`.

    Es la via reactiva: no empuja nada, arma el enlace que el acudiente abre. Sin
    celular no hay enlace, y eso es un fallo de envio (no una excepcion): el
    repartidor lo reintenta o cae a correo segun la preferencia.
    """

    async def enviar(self, contacto: Contacto, plantilla: str, datos: dict[str, object]) -> Envio:
        if not contacto.celular:
            return Envio(canal="wa_link", exito=False, detalle="sin_celular")
        numero = "".join(c for c in contacto.celular if c.isdigit())
        mensaje = urllib.parse.quote(texto_de(plantilla, datos))
        enlace = f"https://wa.me/{numero}?text={mensaje}"
        return Envio(canal="wa_link", exito=True, enlace=enlace)


@dataclass
class Correo:
    """Correo (FU-02). Por omision imprime a consola (desarrollo); con SMTP
    configurado por entorno, envia de verdad.

    Las variables SMTP salen del entorno (`TUKIT_SMTP_HOST`, `_PORT`, `_USER`,
    `_PASSWORD`, `_DESDE`), mismo idioma que el resto de la configuracion. Sin
    host configurado, el modo consola deja el aviso en el log sin fingir que
    salio: es honesto sobre que no hay servidor detras.
    """

    remitente: str = ""

    def _smtp_host(self) -> str | None:
        return os.environ.get("TUKIT_SMTP_HOST") or None

    def _armar(self, destino: str, plantilla: str, datos: dict[str, object]) -> EmailMessage:
        desde = self.remitente or os.environ.get("TUKIT_SMTP_DESDE", "no-responder@tukit.co")
        mensaje = EmailMessage()
        mensaje["From"] = desde
        mensaje["To"] = destino
        mensaje["Subject"] = asunto_de(plantilla)
        mensaje.set_content(texto_de(plantilla, datos))
        cuerpo_html = html_de(plantilla, datos)
        if cuerpo_html:
            mensaje.add_alternative(cuerpo_html, subtype="html")
        return mensaje

    async def enviar(self, contacto: Contacto, plantilla: str, datos: dict[str, object]) -> Envio:
        if not contacto.correo:
            return Envio(canal="correo", exito=False, detalle="sin_correo")
        try:
            mensaje = self._armar(contacto.correo, plantilla, datos)
            host = self._smtp_host()
            if host is None:
                return self._enviar_consola(contacto.usuario_id, mensaje)
            # `smtplib.SMTP` es bloqueante (socket + starttls + login); correrlo tal
            # cual dentro de este `async` congelaria el event loop —y con el la cola
            # del repartidor— mientras un servidor de correo lento responde. Se corre
            # en un hilo para que solo espere quien envia, no todo el servicio.
            return await asyncio.to_thread(self._enviar_smtp, host, mensaje)
        except Exception as error:  # noqa: BLE001 - un correo nunca tumba al repartidor
            _log.warning("correo no enviado (%s): %s", plantilla, type(error).__name__)
            return Envio(canal="correo", exito=False, detalle=f"error: {type(error).__name__}")

    def _enviar_consola(self, usuario_id: str, mensaje: EmailMessage) -> Envio:
        """Sin servidor: deja el aviso en el log y, si hay buzon, el .eml completo.
        No finge que salio: el detalle dice `consola`. El destinatario NO se imprime."""
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
    """Registra lo enviado sin salir a ninguna parte. Para pruebas y desarrollo.

    Guarda tuplas (usuario_id, plantilla, canal, texto) para que una prueba
    compruebe que se envio exactamente uno y que el texto NO trae el contacto.
    """

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
    """Elige canal por preferencia: wa-link si hay celular, si no correo.

    En v1 la preferencia por usuario aun no gobierna (no hay pantalla que la
    fije); la heuristica es "wa-link si el contacto trae celular, correo en otro
    caso", con caida a correo si wa-link no pudo. Cuando exista
    `preferencia_notificacion` con datos, este selector la lee sin tocar el
    puerto.
    """

    wa: Notificador = field(default_factory=WaLink)
    correo: Notificador = field(default_factory=Correo)

    async def enviar(self, contacto: Contacto, plantilla: str, datos: dict[str, object]) -> Envio:
        if contacto.celular:
            envio = await self.wa.enviar(contacto, plantilla, datos)
            if envio.exito:
                return envio
        return await self.correo.enviar(contacto, plantilla, datos)


def notificador_desde_entorno() -> Notificador:
    """El notificador compuesto por omision: wa-link + correo (consola o SMTP)."""
    return NotificadorCompuesto()


__all__ = [
    "Notificador",
    "NotificadorCompuesto",
    "NotificadorFalso",
    "WaLink",
    "Correo",
    "Contacto",
    "Envio",
    "texto_de",
    "asunto_de",
    "html_de",
    "notificador_desde_entorno",
]
