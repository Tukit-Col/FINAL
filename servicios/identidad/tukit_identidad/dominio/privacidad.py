"""Las reglas puras del panel de privacidad (Ley 1581 de 2012, Decreto 1377 de 2013).

Tres cosas que no tocan la base y por eso viven aqui:

- **Enmascarar el contacto.** El inventario le muestra al titular que dato
  tenemos sin repetirlo entero en una pantalla que se puede fotografiar o
  quedar abierta. La exportacion si lo lleva completo: es su copia.
- **La confirmacion escrita.** Suprimir no tiene vuelta atras, asi que se pide
  una frase exacta. Se compara sin mayusculas, sin tildes y con los espacios
  colapsados, porque lo que se quiere probar es intencion, no ortografia.
- **Lo que se borra y lo que se conserva, con su fundamento.** La respuesta de
  la supresion y la pantalla del panel leen la misma lista, asi que no pueden
  contar historias distintas.
"""

from __future__ import annotations

import unicodedata

FRASE_CONFIRMACION = "ELIMINAR MIS DATOS"


def _normalizar(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return " ".join(sin_tildes.upper().split())


def confirmacion_valida(texto: str | None) -> bool:
    """¿Escribio el titular la frase de confirmacion?"""
    return texto is not None and _normalizar(texto) == FRASE_CONFIRMACION


def enmascarar_correo(correo: str | None) -> str | None:
    """`ana.maria@ejemplo.com` -> `a***@ejemplo.com`. Sin arroba, todo tapado."""
    if not correo:
        return None
    usuario, arroba, dominio = correo.partition("@")
    if not arroba or not usuario:
        return "***"
    return f"{usuario[0]}***@{dominio}"


def enmascarar_telefono(telefono: str | None) -> str | None:
    """Deja ver solo los ultimos cuatro digitos: `*** *** 4567`."""
    if not telefono:
        return None
    digitos = [c for c in telefono if c.isdigit()]
    if len(digitos) <= 4:
        return "****"
    return "*** *** " + "".join(digitos[-4:])


def correo_suprimido(usuario_id: str) -> str:
    """El correo que queda en la fila anonimizada. `.invalid` es un dominio
    reservado (RFC 2606): nunca le llega un correo a nadie, y como lleva el id
    no choca con el indice unico del correo."""
    return f"suprimido-{usuario_id}@tukit.invalid"


# Lo que la supresion borra de Identidad. Va en palabras del titular.
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

# Lo que la ley obliga a conservar. No se borra: se desvincula de la persona.
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
