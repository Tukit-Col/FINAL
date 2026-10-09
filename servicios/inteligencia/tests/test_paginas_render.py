"""NFR-MAN-01: De un archivo a una imagen por pagina: conteo, tope, resolucion y formato de salida.

`paginas.renderizar` es el puerto que separa la percepcion de la libreria de
render. Su contrato es corto y se rompe en silencio si cambia: una imagen suelta
ya es una pagina y no se toca; un PDF produce UN PNG por pagina, EN ORDEN, a la
resolucion pedida (150 DPI por omision, lo que hace legible una tabla de
utiles); y el documento se cierra pase lo que pase. El tope de paginas
(`TOPE_PAGINAS`, 40) lo impone `percepcion.percibir` sobre ese conteo, y rechaza
el archivo ENTERO: nunca se leen las primeras y se devuelve el resto como si
fuera la lista completa.

`pypdfium2` no es una dependencia del entorno de pruebas (es el extra `pdf` del
servicio), asi que se sustituye en `sys.modules` por un doble que dibuja paginas
con Pillow: lo que se verifica es lo que `renderizar` hace con la libreria (la
escala, el orden, el formato PNG, el cierre), no el render de pdfium. Las
imagenes sueltas se generan con Pillow, que si esta instalado.
"""

from __future__ import annotations

import io
import sys
import types
from typing import Any

import pytest
from PIL import Image
from tukit_inteligencia import paginas
from tukit_inteligencia.percepcion import TOPE_PAGINAS, ItemExtraido, PaginaLeida, percibir

pytestmark = pytest.mark.nfr("NFR-MAN-01")

FIRMA_PNG = b"\x89PNG\r\n\x1a\n"
PDF = b"%PDF-1.7\n% archivo ficticio de prueba\n"
COLORES = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]


def _imagen(
    formato: str, tamano: tuple[int, int] = (20, 10), color: tuple[int, int, int] = (9, 9, 9)
) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", tamano, color).save(buffer, format=formato)
    return buffer.getvalue()


class _Bitmap:
    def __init__(self, imagen: Image.Image) -> None:
        self._imagen = imagen

    def to_pil(self) -> Image.Image:
        return self._imagen


class _Pagina:
    def __init__(self, indice: int, ancho: int, alto: int, falla: bool) -> None:
        self.indice = indice
        self.ancho, self.alto = ancho, alto
        self.falla = falla
        self.escalas: list[float] = []
        self.cerrada = False

    def render(self, *, scale: float) -> _Bitmap:
        if self.falla:
            raise RuntimeError(f"pdfium no pudo dibujar la pagina {self.indice + 1}")
        self.escalas.append(scale)
        color = COLORES[self.indice % len(COLORES)]
        return _Bitmap(Image.new("RGB", (round(self.ancho * scale), round(self.alto * scale)), color))

    def close(self) -> None:
        self.cerrada = True


class _Documento:
    def __init__(self, contenido: bytes, n: int, ancho: int, alto: int, falla_en: int | None) -> None:
        self.contenido = contenido
        self.paginas = [_Pagina(i, ancho, alto, i == falla_en) for i in range(n)]
        self.cerrado = False

    def __len__(self) -> int:
        return len(self.paginas)

    def __getitem__(self, indice: int) -> _Pagina:
        return self.paginas[indice]

    def close(self) -> None:
        self.cerrado = True


def _instalar_pdfium(
    monkeypatch, *, paginas_: int, ancho: int = 72, alto: int = 144, falla_en: int | None = None
) -> list[_Documento]:
    """Pone un `pypdfium2` falso en `sys.modules`. Devuelve los documentos que se abran."""
    abiertos: list[_Documento] = []
    modulo = types.ModuleType("pypdfium2")

    def _pdf_document(contenido: bytes) -> _Documento:
        documento = _Documento(contenido, paginas_, ancho, alto, falla_en)
        abiertos.append(documento)
        return documento

    modulo.PdfDocument = _pdf_document  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pypdfium2", modulo)
    return abiertos


def _abrir(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png))


class TestUnaImagenYaEsUnaPagina:
    @pytest.mark.parametrize("formato", ["PNG", "JPEG", "WEBP"])
    def test_se_devuelve_tal_cual_sin_tocar_los_bytes(self, monkeypatch, formato):
        """jpg, png y webp ya son una pagina: recomprimirlos perderia calidad para la lectura."""
        monkeypatch.setitem(sys.modules, "pypdfium2", None)  # si intentara importar el render, fallaria
        original = _imagen(formato)

        resultado = paginas.renderizar(original)

        assert resultado == [original]
        assert resultado[0] is original

    def test_solo_la_firma_pdf_al_inicio_activa_el_render(self, monkeypatch):
        """La decision es por el contenido, no por la extension: bytes que no abren con `%PDF` son imagen."""
        monkeypatch.setitem(sys.modules, "pypdfium2", None)
        contenido = b"  %PDF-1.7 con espacios delante"

        assert paginas.renderizar(contenido) == [contenido]


class TestUnPdfDaUnPngPorPagina:
    def test_un_png_por_pagina_en_orden(self, monkeypatch):
        _instalar_pdfium(monkeypatch, paginas_=3)

        salida = paginas.renderizar(PDF)

        assert len(salida) == 3
        assert all(p.startswith(FIRMA_PNG) for p in salida)
        imagenes = [_abrir(p) for p in salida]
        assert [i.format for i in imagenes] == ["PNG"] * 3
        # El orden de las paginas se conserva: cada una trae su color.
        assert [i.convert("RGB").getpixel((0, 0)) for i in imagenes] == COLORES[:3]

    def test_a_150_dpi_por_omision_una_pagina_de_72_puntos_mide_150_pixeles(self, monkeypatch):
        """150 DPI = escala 150/72: es la resolucion con la que una tabla de utiles se lee como tabla."""
        documentos = _instalar_pdfium(monkeypatch, paginas_=1, ancho=72, alto=144)

        (png,) = paginas.renderizar(PDF)

        assert documentos[0].paginas[0].escalas == [150 / 72]
        assert _abrir(png).size == (150, 300)

    def test_el_dpi_pedido_cambia_la_escala(self, monkeypatch):
        documentos = _instalar_pdfium(monkeypatch, paginas_=1, ancho=72, alto=144)

        (png,) = paginas.renderizar(PDF, dpi=300)

        assert documentos[0].paginas[0].escalas == [300 / 72]
        assert _abrir(png).size == (300, 600)

    def test_el_documento_recibe_los_bytes_del_archivo(self, monkeypatch):
        documentos = _instalar_pdfium(monkeypatch, paginas_=1)

        paginas.renderizar(PDF)

        assert documentos[0].contenido == PDF

    def test_un_pdf_sin_paginas_da_una_lista_vacia(self, monkeypatch):
        """No inventa una pagina en blanco: `percibir` lo rechaza como `pdf_sin_paginas`."""
        documentos = _instalar_pdfium(monkeypatch, paginas_=0)

        assert paginas.renderizar(PDF) == []
        assert documentos[0].cerrado

    def test_cierra_cada_pagina_y_el_documento(self, monkeypatch):
        documentos = _instalar_pdfium(monkeypatch, paginas_=3)

        paginas.renderizar(PDF)

        assert documentos[0].cerrado
        assert all(p.cerrada for p in documentos[0].paginas)

    def test_si_una_pagina_no_se_dibuja_el_error_sale_y_el_documento_se_cierra(self, monkeypatch):
        """No se devuelven las primeras paginas como si fueran toda la lista: el fallo se propaga."""
        documentos = _instalar_pdfium(monkeypatch, paginas_=3, falla_en=1)

        with pytest.raises(RuntimeError, match="pagina 2"):
            paginas.renderizar(PDF)

        assert documentos[0].cerrado  # la fuga de un handle de pdfium se acumula en un worker de larga vida

    def test_sin_pypdfium2_el_error_dice_que_instalar(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pypdfium2", None)

        with pytest.raises(RuntimeError, match="pypdfium2") as info:
            paginas.renderizar(PDF)

        assert "extra `pdf`" in str(info.value)
        assert isinstance(info.value.__cause__, ImportError)


class TestConLaPercepcion:
    """`percibir` impone el tope sobre el conteo que da `renderizar`."""

    @staticmethod
    def _lector(vistas: list[tuple[bytes, int]]) -> Any:
        def _leer(png: bytes, numero: int) -> PaginaLeida:
            vistas.append((png, numero))
            return PaginaLeida(grados=["Cuarto"], items=[ItemExtraido(descripcion=f"item {numero}")])

        return _leer

    def test_una_imagen_suelta_es_un_archivo_de_una_pagina(self):
        original = _imagen("PNG", (30, 30))
        vistas: list[tuple[bytes, int]] = []

        resultado = percibir(original, renderizar=paginas.renderizar, leer=self._lector(vistas))

        assert resultado.aceptada is True
        assert resultado.paginas == 1
        assert vistas == [(original, 1)]  # el modelo recibe exactamente los bytes subidos

    def test_un_pdf_se_lee_pagina_por_pagina_y_en_orden(self, monkeypatch):
        _instalar_pdfium(monkeypatch, paginas_=3, ancho=36, alto=36)
        vistas: list[tuple[bytes, int]] = []

        resultado = percibir(PDF, renderizar=paginas.renderizar, leer=self._lector(vistas))

        assert resultado.aceptada is True
        assert resultado.paginas == 3
        assert [numero for _png, numero in vistas] == [1, 2, 3]
        assert all(png.startswith(FIRMA_PNG) for png, _numero in vistas)
        assert [i.descripcion for i in resultado.items] == ["item 1", "item 2", "item 3"]

    def test_el_tope_exacto_se_lee_completo(self, monkeypatch):
        _instalar_pdfium(monkeypatch, paginas_=TOPE_PAGINAS, ancho=8, alto=8)
        vistas: list[tuple[bytes, int]] = []

        resultado = percibir(PDF, renderizar=paginas.renderizar, leer=self._lector(vistas))

        assert resultado.aceptada is True
        assert resultado.paginas == TOPE_PAGINAS == 40
        assert len(vistas) == 40

    def test_pasado_el_tope_se_rechaza_el_archivo_entero_sin_llamar_al_modelo(self, monkeypatch):
        """Una pagina de mas no recorta: ni una sola pagina llega al modelo y se dice cuantas hay."""
        _instalar_pdfium(monkeypatch, paginas_=TOPE_PAGINAS + 1, ancho=8, alto=8)
        vistas: list[tuple[bytes, int]] = []

        resultado = percibir(PDF, renderizar=paginas.renderizar, leer=self._lector(vistas))

        assert resultado.aceptada is False
        assert resultado.error == "archivo_demasiado_largo"
        assert resultado.paginas == 41
        assert "41 paginas" in resultado.mensaje
        assert vistas == []

    def test_un_pdf_sin_paginas_se_rechaza(self, monkeypatch):
        _instalar_pdfium(monkeypatch, paginas_=0)

        resultado = percibir(PDF, renderizar=paginas.renderizar, leer=self._lector([]))

        assert (resultado.aceptada, resultado.error) == (False, "pdf_sin_paginas")

    def test_un_pdf_que_el_render_no_abre_es_ilegible_con_la_causa(self, monkeypatch):
        modulo = types.ModuleType("pypdfium2")

        def _roto(_contenido: bytes) -> Any:
            raise RuntimeError("Failed to load document (PDFium: Data format error)")

        modulo.PdfDocument = _roto  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "pypdfium2", modulo)

        resultado = percibir(b"%PDF-truncado", renderizar=paginas.renderizar, leer=self._lector([]))

        assert resultado.aceptada is False
        assert resultado.error == "pdf_ilegible"
        assert "Data format error" in resultado.mensaje

    def test_sin_el_extra_pdf_un_pdf_es_ilegible_y_dice_que_instalar(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pypdfium2", None)

        resultado = percibir(PDF, renderizar=paginas.renderizar, leer=self._lector([]))

        assert resultado.error == "pdf_ilegible"
        assert "pypdfium2" in resultado.mensaje

    def test_un_archivo_vacio_ni_se_renderiza(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pypdfium2", None)

        resultado = percibir(b"", renderizar=paginas.renderizar, leer=self._lector([]))

        assert (resultado.aceptada, resultado.error) == (False, "archivo_vacio")
