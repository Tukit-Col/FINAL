"""De un PDF a una imagen por pagina.

Vive aparte de la percepcion porque es un detalle de libreria: si manana
cambia el motor de render, las reglas de grados no se enteran. Una imagen
suelta (jpg, png, webp) ya es una pagina y no se toca.
"""

from __future__ import annotations

import io


def renderizar(contenido: bytes, *, dpi: int = 150) -> list[bytes]:
    """Una imagen PNG por pagina, a 150 DPI, que es como se leia antes.

    150 DPI alcanza para que una tabla de utiles se lea como tabla. Mas
    resolucion sube el costo de cada llamada y no cambia lo que el modelo
    alcanza a ver en una lista escolar.
    """
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
