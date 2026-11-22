from __future__ import annotations

import unicodedata

FRASE_CONFIRMACION = "ELIMINAR MIS DATOS"


def _normalizar(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return " ".join(sin_tildes.upper().split())


def confirmacion_valida(texto: str | None) -> bool:
    return texto is not None and _normalizar(texto) == FRASE_CONFIRMACION


def enmascarar_correo(correo: str | None) -> str | None:
    if not correo:
        return None
    usuario, arroba, dominio = correo.partition("@")
    if not arroba or not usuario:
        return "***"
    return f"{usuario[0]}***@{dominio}"


def enmascarar_telefono(telefono: str | None) -> str | None:
    if not telefono:
        return None
    digitos = [c for c in telefono if c.isdigit()]
    if len(digitos) <= 4:
        return "****"
    return "*** *** " + "".join(digitos[-4:])


def correo_suprimido(usuario_id: str) -> str:
    return f"suprimido-{usuario_id}@tukit.invalid"


SUPRIMIDO: tuple[dict[str, str], ...] = (
    {"dato": "nombre", "detalle": "Tu nombre."},
    {"dato": "correo", "detalle": "Tu correo. Ya no podras entrar con el."},
    {"dato": "celular", "detalle": "Tu numero de celular."},
    {"dato": "clave", "detalle": "Tu clave. La cuenta queda cerrada y tu sesion termina."},
    {"dato": "direcciones", "detalle": "Todas las direcciones de tu libreta, con sus contactos."},
    {"dato": "hijos", "detalle": "Los apodos de tus hijos y sus vinculos con colegio y grado."},
    {"dato": "perfil", "detalle": "Tu perfil socioeconomico, si lo diligenciaste."},
    {"dato": "consentimientos", "detalle": "Tus autorizaciones quedan revocadas desde hoy."},
)

CONSERVADO: tuple[dict[str, str], ...] = (
    {
        "dato": "pedidos_y_facturas",
        "detalle": (
            "Tus pedidos, pagos y facturas se conservan por diez anos, pero quedan "
            "con un identificador que ya no lleva a tu nombre, correo ni celular."
        ),
        "fundamento": (
            "Estatuto Tributario, articulo 632, y Codigo de Comercio, articulo 60: "
            "los soportes contables se conservan diez anos."
        ),
    },
    {
        "dato": "garantia",
        "detalle": ("Lo necesario para atender la garantia o un retracto de un producto que ya compraste."),
        "fundamento": (
            "Ley 1480 de 2011 (Estatuto del Consumidor), articulos 7 y 47: garantia "
            "legal y derecho de retracto."
        ),
    },
    {
        "dato": "registro_de_la_solicitud",
        "detalle": ("Un registro de que pediste la supresion y cuando, sin tu nombre ni tu correo."),
        "fundamento": (
            "Ley 1581 de 2012, articulo 17, y Decreto 1377 de 2013: el responsable "
            "debe poder demostrar que atendio la solicitud."
        ),
    },
)
