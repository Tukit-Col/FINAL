from __future__ import annotations

import io
import struct

_FIRMA_PNG = b"\x89PNG\r\n\x1a\n"
# Fragmentos donde un PNG guarda texto libre y metadatos (comentario, autor, EXIF): la imagen no los necesita
# y el nombre de un menor puede viajar en ellos hacia el proveedor de IA (H-C-15).
_FRAGMENTOS_CON_TEXTO = frozenset({b"tEXt", b"iTXt", b"zTXt", b"eXIf"})


def quitar_metadatos(contenido: bytes) -> bytes:
    """Quita de un PNG los fragmentos de texto y metadatos sin re-codificar los pixeles.

    Cualquier otro formato, o un PNG sin esos fragmentos, vuelve tal cual (mismos bytes).
    """
    if not contenido.startswith(_FIRMA_PNG):
        return contenido
    salida = bytearray(_FIRMA_PNG)
    posicion = len(_FIRMA_PNG)
    quito = False
    while posicion + 8 <= len(contenido):
        largo, tipo = struct.unpack(">I4s", contenido[posicion : posicion + 8])
        fin = posicion + 12 + largo
        if fin > len(contenido):
            return contenido  # PNG truncado o corrupto: no se toca
        if tipo in _FRAGMENTOS_CON_TEXTO:
            quito = True
        else:
            salida += contenido[posicion:fin]
        posicion = fin
    return bytes(salida) if quito else contenido


def renderizar(contenido: bytes, *, dpi: int = 150) -> list[bytes]:
    if not contenido.startswith(b"%PDF"):
        return [contenido]

    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError(
            "Para leer un PDF hace falta pypdfium2. Instalalo con el extra `pdf` del servicio."
        ) from exc

    documento = pdfium.PdfDocument(contenido)
    escala = dpi / 72
    paginas: list[bytes] = []
    try:
        for indice in range(len(documento)):
            pagina = documento[indice]
            bitmap = pagina.render(scale=escala)
            imagen = bitmap.to_pil()
            buffer = io.BytesIO()
            imagen.save(buffer, format="PNG")
            paginas.append(buffer.getvalue())
            pagina.close()
    finally:
        documento.close()
    return paginas
