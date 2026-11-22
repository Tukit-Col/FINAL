from __future__ import annotations

import io


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
