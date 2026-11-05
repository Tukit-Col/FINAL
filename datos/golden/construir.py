"""Arma los dorados OCR/RAG de QA: las listas, la respuesta del modelo y lo esperado.

Que mide un dorado. No mide al modelo, porque eso exigiria llamarlo, y estas
pruebas no gastan un peso. Mide **al sistema dada una respuesta del modelo**:
la respuesta queda grabada en `fixtures-modelo/` y las pruebas la sirven en
lugar de Gemini, buscandola por el sha256 de la pagina que llega a `leer`.

Que produce, todo bajo `datos/golden/`:

- `listas/`: una entrada por variante de formato (G01...G10). Todas piden lo
  mismo; cambia la apariencia, el grado escrito y lo que el modelo alcanza a
  ver. Son imagenes porque el stack no lee PDF sin el extra `pdf` de
  inteligencia (H-A-36 de QA); el unico PDF es G02, cuyo caso es justamente el
  tope de paginas.
- `fixtures-modelo/Gnn-p1.json` e `indice.json`: la respuesta HTTP que daria
  el proveedor para cada pagina, con el formato de `Tukit-QA/acuerdos.md` 1.2.
- `esperado/Gnn.json`: lo que el sistema tiene que devolver, fila por fila y
  etapa por etapa (percepcion, parseo, emparejamiento).
- `esperado/oracle.json`: pares texto -> concepto para el emparejamiento.

Los nombres son ficticios a proposito: el colegio no existe y ninguna lista
lleva nombre de estudiante.

Determinismo. Las imagenes salen de Pillow con una fuente del sistema
(`FUENTES`) y ruido sembrado; el PDF y el .docx se escriben a mano. Con la
misma version de Pillow y la misma fuente, dos corridas dan los mismos bytes.
En otra maquina pueden cambiar los sha256: basta volver a correr el script,
que reescribe las listas, los fixtures y el indice juntos.

Uso (necesita Pillow, que esta en el entorno de desarrollo):

    .venv/bin/python datos/golden/construir.py
    .venv/bin/python datos/golden/construir.py --comprobar
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import sys
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
MODELO = "gemini-3.5-flash-lite"
DPI = 150
TOPE_PAGINAS = 40  # copia de `tukit_inteligencia.percepcion.TOPE_PAGINAS`
ANCHO, ALTO = 1240, 1754  # A4 a 150 DPI
COLEGIO = "Colegio Ficticio QA Tukit"

# La lista base. Cada renglon dice lo que el modelo "leyo" y lo que el sistema
# tiene que hacer con el en cada etapa. El concepto y el estado del
# emparejamiento son el juicio de quien arma el dorado, no la salida del
# emparejador: por eso sirven de oraculo.
#
# (descripcion, cantidad, confianza, tipo_item, modo, cantidad_base,
#  unidades_por_empaque, concepto, estado, nivel)
BASE = [
    (
        "Cuaderno cuadriculado grande cosido de 100 hojas",
        4,
        0.97,
        "util",
        "mercado_abierto",
        4,
        None,
        "C001",
        "reconocido",
        "facil",
    ),
    ("Lápiz negro HB", 3, 0.96, "util", "mercado_abierto", 3, None, "C002", "reconocido", "exacto"),
    ("Caja de colores x 12", 1, 0.95, "util", "mercado_abierto", 1, 12, "C004", "reconocido", "facil"),
    ("Borrador blanco", 2, 0.95, "util", "mercado_abierto", 2, None, "C005", "reconocido", "facil"),
    ("Tajalápiz metálico", 1, 0.94, "util", "mercado_abierto", 1, None, "C007", "reconocido", "facil"),
    ("Regla de 30 cm", 1, 0.93, "util", "mercado_abierto", 1, None, "C008", "reconocido", "facil"),
    ("Tijeras escolares", 1, 0.93, "util", "mercado_abierto", 1, None, "C013", "reconocido", "facil"),
    ("Pegante en barra grande", 2, 0.92, "util", "mercado_abierto", 2, None, "C016", "reconocido", "exacto"),
    (
        "Block cuadriculado tamaño carta",
        1,
        0.92,
        "util",
        "mercado_abierto",
        1,
        None,
        "C003",
        "reconocido",
        "exacto",
    ),
    ("Carpeta con gancho", 2, 0.90, "util", "mercado_abierto", 2, None, "C011", "reconocido", "facil"),
    ("Caja de crayones", 1, 0.90, "util", "mercado_abierto", 1, None, "C053", "reconocido", "facil"),
    ("Diccionario", 1, 0.90, "util", "mercado_abierto", 1, None, "C034", "reconocido", "exacto"),
    # Huecos: lo que el catalogo no puede surtir. El sistema tiene que decir
    # que no lo tiene, nunca poner otro producto en su lugar (NFR-PRE-04).
    ("Chaquiras de colores", 1, 0.88, "util", "mercado_abierto", 1, None, None, "sin_match", "hueco"),
    (
        "Paquete de arena decorativa",
        1,
        0.88,
        "util",
        "mercado_abierto",
        1,
        None,
        "C095",
        "hueco_catalogo",
        "hueco",
    ),
    ("Compás de precisión", 1, 0.90, "util", "mercado_abierto", 1, None, "C018", "abstencion", "hueco"),
    # Informativos: no se compran en Tukit, pero el kit los tiene que mostrar.
    (
        "Plataforma de inglés: código de acceso",
        1,
        0.90,
        "licencia_digital",
        "plataforma",
        1,
        None,
        None,
        "sin_match",
        "informativo",
    ),
    (
        "Uniforme de educación física",
        1,
        0.90,
        "uniforme",
        "mercado_abierto",
        1,
        None,
        None,
        "sin_match",
        "informativo",
    ),
    (
        "Diccionario de inglés: el disponible en casa",
        None,
        0.85,
        "no_comprar",
        "mercado_abierto",
        0,
        None,
        "C034",
        "abstencion",
        "informativo",
    ),
]

# G05: la letra a mano baja la confianza de algunos renglones por debajo del
# umbral con que la consola marca "confianza baja" (0,6) y del tau del
# emparejamiento (0,75). Son los renglones que NFR-PRE-05 espera ver en revision.
CONFIANZA_MANUSCRITO = {2: 0.41, 5: 0.47, 8: 0.52, 11: 0.55}

# Pares de mas para el oraculo: formas que se ven en listas reales y que el
# emparejador no tiene por que acertar. Su top-1 se reporta, no se exige.
DIFICILES = [
    ("Goma de borrar", "C005"),
    ("Sacapuntas metálico", "C007"),
    ("Lápices de colores largos", "C004"),
    ("Crayolas gruesas", "C053"),
    ("Colbón en barra", "C016"),
    ("Cuaderno ferrocarril de 50 hojas", "C001"),
    ("Hojas cuadriculadas en block", "C003"),
    ("Folder con gancho legajador", "C011"),
]

# Recalibracion del oraculo por cambios del catalogo (re-base de QA a `d4ea7cb`,
# 2026-10-11). El oraculo se mide contra `datos/catalogo/` de hoy, y estos tres
# renglones de la lista base cambiaron porque cambio el catalogo, no el
# emparejador. Va solo al oraculo: `esperado/Gnn.json` conserva la respuesta
# grabada que sirven las pruebas de inteligencia (`test_golden_kits.py`), que no
# leen el catalogo. Por el texto de la lista base, con el commit que lo cambio:
RECALIBRADO_CATALOGO = {
    # 44309fa (atributos corregidos a mano): TK-C018-PRE, "Compas Precision Faber
    # Castell", declara tipo=precision. El hueco por atributo dejo de existir y el
    # renglon se surte con el compas de precision.
    "Compás de precisión": {"estado": "reconocido", "concepto": "C018", "nivel": "facil"},
    # 44309fa: C133 "Plan lector virtual", tipo licencia_digital (plataforma Raz
    # Plus, plataforma de lectura). Se reconoce y no tiene producto: sigue sin
    # comprarse en Tukit.
    "Plataforma de inglés: código de acceso": {"estado": "hueco_catalogo", "concepto": "C133"},
    # 44309fa: C131 "Uniforme", tipo uniforme, con el sinonimo "uniforme de
    # educacion fisica". Se reconoce y no tiene producto.
    "Uniforme de educación física": {"estado": "hueco_catalogo", "concepto": "C131"},
    # oe5 (dd7c9a3, e3c7ad1; C034 en b6b6fe7): C034 "Diccionario" lleva ahora los
    # sinonimos de diccionario de ingles. El catalogo lo reconoce y trae productos;
    # sigue sin comprarse porque el parseo lo deja en no_comprar con cantidad 0 y
    # el optimizador no compra ese tipo (TIPOS_NO_COMPRABLES).
    "Diccionario de inglés: el disponible en casa": {"estado": "reconocido", "concepto": "C034"},
}

VARIANTES = {
    "G01": ("G01-tabla-limpia.png", "Tabla limpia, con columna de cantidad"),
    "G02": ("G02-multipagina.pdf", f"PDF de {TOPE_PAGINAS + 1} paginas: pasa el tope sin llamar al modelo"),
    "G03": ("G03-foto-borrosa.jpg", "Foto de la tabla: girada, desenfocada y con grano"),
    "G04": ("G04-word.docx", "Documento de Word: no es imagen ni PDF; el proveedor responde 400"),
    "G05": ("G05-manuscrito.jpg", "Lista escrita a mano en hoja rayada; cuatro renglones con confianza baja"),
    "G06": ("G06-sin-columna-cantidad.png", "Sin columna de cantidad: el numero va dentro del texto"),
    "G07": ("G07-fila-partida.png", "Una descripcion partida en dos renglones"),
    "G08": ("G08-pagina-cortada.png", "Foto cortada: el modelo solo ve la primera mitad"),
    "G09": ("G09-acentos-y-mayusculas.png", "Todo en mayusculas, con tildes"),
    "G10": ("G10-grados-variados.png", "Varios grados en la misma hoja (Cuarto, 4°, Pre-Jardín, 3 A)"),
}

# Grado escrito en cada variante (lo que lee el modelo) y su forma canonica.
GRADO_LEIDO = {
    "G01": ["Tercero"],
    "G03": ["3°"],
    "G05": ["Grado tercero"],
    "G06": ["3"],
    "G07": ["Tercero de primaria"],
    "G08": ["Tercero"],
    "G09": ["TERCERO"],
    "G10": ["Cuarto", "4°", "Pre-Jardín", "3 A"],
}
GRADO_CANONICO = {"G10": ["Cuarto", "Prejardin", "Tercero"]}


# --------------------------------------------------------------- renglones por variante
def _item(descripcion: str, cantidad: int | None, confianza: float) -> dict:
    return {"descripcion": descripcion, "cantidad": cantidad, "confianza": confianza}


def leidos(variante: str) -> list[dict]:
    """Los items tal como los devuelve el modelo en el fixture de la variante."""
    base = [_item(d, c, f) for d, c, f, *_ in BASE]
    if variante in ("G01", "G07"):
        items = base
    elif variante == "G03":
        items = [{**i, "confianza": round(i["confianza"] - 0.08, 2)} for i in base]
    elif variante == "G05":
        items = [
            {**i, "confianza": CONFIANZA_MANUSCRITO.get(n, round(i["confianza"] - 0.05, 2))}
            for n, i in enumerate(base, start=1)
        ]
    elif variante == "G06":
        items = [
            {
                **i,
                "descripcion": f"{i['cantidad']} {i['descripcion']}" if i["cantidad"] else i["descripcion"],
                "cantidad": None,
            }
            for i in base
        ]
    elif variante == "G08":
        items = base[:9]
    elif variante == "G09":
        items = [{**i, "descripcion": i["descripcion"].upper()} for i in base]
    elif variante == "G10":
        items = [base[0], base[1], base[3], base[5], base[6], base[9]]
    else:
        raise ValueError(variante)
    if variante == "G07":
        # El modelo une la descripcion partida y deja un renglon vacio donde
        # estaba la continuacion. La percepcion lo tiene que descartar.
        items = items[:1] + [_item("   ", None, 0.30)] + items[1:]
    return items


def _origen(variante: str) -> list[tuple]:
    """Las filas de `BASE` que la variante deja ver, en su orden."""
    if variante == "G08":
        return BASE[:9]
    if variante == "G10":
        return [BASE[n] for n in (0, 1, 3, 5, 6, 9)]
    return BASE


def renglones_esperados(variante: str) -> list[dict]:
    """Lo que cada etapa tiene que producir para cada renglon que sobrevive a la percepcion."""
    filas = []
    leidos_sin_vacios = [i for i in leidos(variante) if i["descripcion"].strip()]
    for orden, (item, fila) in enumerate(zip(leidos_sin_vacios, _origen(variante), strict=True), start=1):
        _, _, _, tipo, modo, cantidad, empaque, concepto, estado, nivel = fila
        filas.append(
            {
                "orden": orden,
                "texto": item["descripcion"],
                "parseo": {
                    "tipo_item": tipo,
                    "modo_adquisicion": modo,
                    "cantidad": cantidad,
                    "unidades_por_empaque": empaque,
                },
                "emparejamiento": {"estado": estado, "concepto": concepto, "nivel": nivel},
            }
        )
    return filas


# --------------------------------------------------------------- dibujo
# La fuente que Pillow trae embebida no tiene tildes ni enes, y una lista
# escolar sin "Lapiz" con tilde no se parece a una lista escolar. Se usa la
# primera que exista; la que salio queda anotada en cada fixture (`render`).
FUENTES = {
    "tabla": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ],
    "mano": [
        "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    ],
}


def ruta_fuente(clase: str = "tabla") -> str | None:
    for ruta in FUENTES[clase] + (FUENTES["tabla"] if clase != "tabla" else []):
        if Path(ruta).exists():
            return ruta
    return None


def _fuente(tamano: int, clase: str = "tabla"):
    from PIL import ImageFont

    ruta = ruta_fuente(clase)
    return ImageFont.truetype(ruta, tamano) if ruta else ImageFont.load_default(size=tamano)


def _hoja():
    from PIL import Image

    return Image.new("RGB", (ANCHO, ALTO), "white")


def _encabezado(dibujo, grado: str) -> int:
    dibujo.text((90, 70), COLEGIO, font=_fuente(40), fill="black")
    dibujo.text(
        (90, 130),
        f"Lista de útiles escolares · Año lectivo 2027 · Grado {grado}",
        font=_fuente(26),
        fill="black",
    )
    dibujo.line((90, 180, ANCHO - 90, 180), fill="black", width=2)
    return 210


def _tabla(dibujo, filas: list[tuple[str, str]], y: int, *, con_cantidad: bool = True) -> int:
    fuente = _fuente(24)
    alto = 52
    izquierda, derecha, corte = 90, ANCHO - 90, 220
    dibujo.rectangle((izquierda, y, derecha, y + alto), fill=(225, 225, 225), outline="black")
    if con_cantidad:
        dibujo.text((izquierda + 20, y + 14), "Cant.", font=fuente, fill="black")
        dibujo.text((corte + 20, y + 14), "Descripción", font=fuente, fill="black")
    else:
        dibujo.text((izquierda + 20, y + 14), "Útiles", font=fuente, fill="black")
    y += alto
    for cantidad, texto in filas:
        lineas = texto.split("\n")
        alto_fila = alto + 30 * (len(lineas) - 1)
        dibujo.rectangle((izquierda, y, derecha, y + alto_fila), outline="black")
        if con_cantidad:
            dibujo.line((corte, y, corte, y + alto_fila), fill="black")
            dibujo.text((izquierda + 20, y + 14), cantidad, font=fuente, fill="black")
        for n, linea in enumerate(lineas):
            dibujo.text(
                ((corte if con_cantidad else izquierda) + 20, y + 14 + 30 * n),
                linea,
                font=fuente,
                fill="black",
            )
        y += alto_fila
    return y


def _cantidad(i: dict) -> str:
    return "" if i["cantidad"] is None else str(i["cantidad"])


def _filas_de(items: list[dict]) -> list[tuple[str, str]]:
    return [(_cantidad(i), i["descripcion"]) for i in items if i["descripcion"].strip()]


def _png(imagen) -> bytes:
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


def _jpg(imagen) -> bytes:
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=70)
    return buffer.getvalue()


def _tabla_limpia(grado: str, filas: list[tuple[str, str]], *, con_cantidad: bool = True):
    from PIL import ImageDraw

    hoja = _hoja()
    dibujo = ImageDraw.Draw(hoja)
    _tabla(dibujo, filas, _encabezado(dibujo, grado), con_cantidad=con_cantidad)
    return hoja


def _foto(hoja, semilla: int):
    """Una foto de celular de la hoja: girada, desenfocada y con grano."""
    from PIL import Image, ImageFilter

    azar = random.Random(semilla)
    girada = hoja.rotate(2.2, resample=Image.Resampling.BICUBIC, fillcolor=(205, 200, 190))
    borrosa = girada.filter(ImageFilter.GaussianBlur(1.6))
    # Grano a un tercio de la resolucion: ruido sembrado, y un JPEG que no pesa megas.
    ancho, alto = ANCHO // 3, ALTO // 3
    grano = Image.frombytes("L", (ancho, alto), azar.randbytes(ancho * alto))
    grano = grano.resize((ANCHO, ALTO), Image.Resampling.BILINEAR).convert("RGB")
    return Image.blend(borrosa, grano, 0.12)


def _manuscrito(grado: str, items: list[dict]):
    from PIL import ImageDraw

    azar = random.Random(5)
    hoja = _hoja()
    dibujo = ImageDraw.Draw(hoja)
    for y in range(160, ALTO - 60, 58):
        dibujo.line((60, y, ANCHO - 60, y), fill=(170, 200, 235), width=2)
    dibujo.line((140, 0, 140, ALTO), fill=(235, 160, 160), width=2)
    tinta = (25, 35, 110)
    fuente = _fuente(32, "mano")
    renglones = [f"{COLEGIO} - Útiles {grado}"] + [
        f"{_cantidad(i)}  {i['descripcion']}".strip() for i in items
    ]
    y = 118
    for texto in renglones:
        x = 160.0
        for caracter in texto:
            dibujo.text(
                (x + azar.uniform(-1.5, 1.5), y + azar.uniform(-3, 3)), caracter, font=fuente, fill=tinta
            )
            x += fuente.getlength(caracter) * azar.uniform(0.95, 1.12)
        y += 58
    return hoja


def _grados_variados():
    from PIL import ImageDraw

    hoja = _hoja()
    dibujo = ImageDraw.Draw(hoja)
    dibujo.text((90, 70), COLEGIO, font=_fuente(40), fill="black")
    dibujo.text((90, 130), "Listas de útiles escolares · Año lectivo 2027", font=_fuente(26), fill="black")
    y = 200
    base = [_item(d, c, f) for d, c, f, *_ in BASE]
    for grado, indices in (("Cuarto", (0, 1)), ("4°", (3,)), ("Pre-Jardín", (5, 6)), ("3 A", (9,))):
        dibujo.text((90, y), f"Grado {grado}", font=_fuente(30), fill="black")
        y = _tabla(dibujo, _filas_de([base[n] for n in indices]), y + 50) + 40
    return hoja


def _pdf(paginas: list[list[str]]) -> bytes:
    """Un PDF de texto, escrito a mano para que sus bytes no dependan de ninguna libreria."""

    def literal(texto: str) -> bytes:
        crudo = texto.encode("cp1252")
        return b"(" + crudo.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"

    objetos: list[bytes] = []
    n = len(paginas)
    hijos = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objetos.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objetos.append(f"<< /Type /Pages /Kids [{hijos}] /Count {n} >>".encode())
    fuente = 3 + 2 * n
    for i, lineas in enumerate(paginas):
        flujo = (
            b"BT /F1 14 Tf 60 780 Td 18 TL " + b" ".join(literal(linea) + b" '" for linea in lineas) + b" ET"
        )
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 {fuente} 0 R >> >> >>".encode()
        )
        objetos.append(b"<< /Length " + str(len(flujo)).encode() + b" >>\nstream\n" + flujo + b"\nendstream")
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

    salida = bytearray(b"%PDF-1.4\n")
    posiciones = []
    for numero, cuerpo in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{numero} 0 obj\n".encode() + cuerpo + b"\nendobj\n"
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for posicion in posiciones:
        salida += f"{posicion:010d} 00000 n \n".encode()
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(salida)


def _docx(lineas: list[str]) -> bytes:
    """Un .docx minimo: lo que Word guarda con un parrafo por renglon."""

    def escapar(texto: str) -> str:
        return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    tipos = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    relaciones = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    parrafos = "".join(f"<w:p><w:r><w:t>{escapar(linea)}</w:t></w:r></w:p>" for linea in lineas)
    documento = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{parrafos}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archivo:
        for nombre, texto in (
            ("[Content_Types].xml", tipos),
            ("_rels/.rels", relaciones),
            ("word/document.xml", documento),
        ):
            info = zipfile.ZipInfo(nombre, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archivo.writestr(info, texto.encode())
    return buffer.getvalue()


def entradas() -> dict[str, bytes]:
    """Los bytes de cada lista, por variante."""
    base = [_item(d, c, f) for d, c, f, *_ in BASE]
    filas = _filas_de(base)
    salida: dict[str, bytes] = {}
    salida["G01"] = _png(_tabla_limpia("Tercero", filas))
    salida["G02"] = _pdf(
        [
            [
                f"{COLEGIO} - Lista de utiles 2027",
                f"Pagina {n} de {TOPE_PAGINAS + 1}",
                "",
                *[t for _, t in filas][:6],
            ]
            for n in range(1, TOPE_PAGINAS + 2)
        ]
    )
    salida["G03"] = _jpg(_foto(_tabla_limpia("3°", filas), semilla=3))
    salida["G04"] = _docx(
        [COLEGIO, "Lista de útiles escolares - Grado Tercero", *[f"{c} {t}" for c, t in filas]]
    )
    salida["G05"] = _jpg(_manuscrito("Grado tercero", base))
    salida["G06"] = _png(_tabla_limpia("3", _filas_de(leidos("G06")), con_cantidad=False))
    partidas = list(filas)
    partidas[0] = (partidas[0][0], "Cuaderno cuadriculado grande cosido\nde 100 hojas")
    salida["G07"] = _png(_tabla_limpia("Tercero de primaria", partidas))
    completa = _tabla_limpia("Tercero", filas)
    salida["G08"] = _png(completa.crop((0, 0, ANCHO, 760)))
    salida["G09"] = _png(_tabla_limpia("TERCERO", [(c, t.upper()) for c, t in filas]))
    salida["G10"] = _png(_grados_variados())
    return salida


# --------------------------------------------------------------- fixtures y esperado
def _texto_pagina(variante: str) -> str:
    return json.dumps(
        {
            "grados": GRADO_LEIDO[variante],
            "completa": variante != "G08",
            "items": leidos(variante),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def esperado(variante: str) -> dict:
    """La salida de `percibir` que el dorado exige, mas las etapas siguientes."""
    nombre, descripcion = VARIANTES[variante]
    salida = {"variante": variante, "archivo": f"listas/{nombre}", "descripcion": descripcion}
    if variante == "G02":
        return {
            **salida,
            "aceptada": False,
            "error": "archivo_demasiado_largo",
            "paginas": TOPE_PAGINAS + 1,
            "llamadas_al_modelo": 0,
            "grados": [],
            "completa": None,
            "items": [],
            "renglones": [],
        }
    if variante == "G04":
        return {
            **salida,
            "aceptada": False,
            "error": "percepcion_fallida",
            "paginas": 1,
            "degradaciones": ["gemini"],
            "grados": [],
            "completa": None,
            "items": [],
            "renglones": [],
        }
    items = [i for i in leidos(variante) if i["descripcion"].strip()]
    error = {"G08": "pagina_incompleta", "G10": "lista_de_varios_grados"}.get(variante)
    return {
        **salida,
        "aceptada": error is None,
        "error": error,
        "paginas": 1,
        "degradaciones": ["pagina_1_incompleta"] if variante == "G08" else [],
        "grados": GRADO_CANONICO.get(variante, ["Tercero"]),
        "completa": variante != "G08",
        "items": items,
        "renglones": renglones_esperados(variante),
    }


def fixture(variante: str, contenido: bytes) -> dict:
    from PIL import __version__ as pillow

    nombre, _ = VARIANTES[variante]
    ensayos = ["NFR-PRE-01", "NFR-PRE-02", "NFR-PRE-03", "NFR-PRE-04", "NFR-COS-01"]
    if variante == "G05":
        ensayos.append("NFR-PRE-05")
    if variante == "G04":
        respuesta = {
            "status": 400,
            "demora_s": 0,
            "cuerpo": json.dumps(
                {
                    "error": {
                        "code": 400,
                        "message": "Provided image is not valid.",
                        "status": "INVALID_ARGUMENT",
                    }
                }
            ),
        }
    else:
        respuesta = {
            "status": 200,
            "demora_s": 0,
            "cuerpo": {"candidates": [{"content": {"parts": [{"text": _texto_pagina(variante)}]}}]},
        }
    previsto = esperado(variante)
    return {
        "fixture_id": f"{variante}-p1",
        "origen": "sintetico",
        "ensayo_ids": ensayos,
        "archivo": f"datos/golden/listas/{nombre}",
        "pagina": 1,
        "sha256_pagina": hashlib.sha256(contenido).hexdigest(),
        "render": {
            "pillow": pillow,
            "dpi": DPI,
            "fuente": (
                "no aplica: no es una imagen"
                if variante == "G04"
                else Path(ruta_fuente("mano" if variante == "G05" else "tabla") or "embebida de Pillow").name
            ),
            "nota": "no empieza con %PDF: llega a leer tal cual (paginas.py:20-21)",
        },
        "modelo": MODELO,
        "respuesta_http": respuesta,
        "esperado": {
            "error": previsto["error"],
            "items": len(previsto["items"]),
            "grados": previsto["grados"],
        },
    }


def oraculo() -> dict:
    """Pares texto -> concepto, de todos los renglones de las variantes y de `DIFICILES`."""
    pares: dict[str, dict] = {}
    for variante in ("G01", "G03", "G05", "G06", "G07", "G08", "G09", "G10"):
        for fila, base in zip(renglones_esperados(variante), _origen(variante), strict=True):
            e = {**fila["emparejamiento"], **RECALIBRADO_CATALOGO.get(base[0], {})}
            nivel = e["nivel"]
            if variante in ("G06", "G09") and nivel in ("exacto", "facil"):
                nivel = "dificil"
            par = pares.setdefault(
                fila["texto"],
                {
                    "texto": fila["texto"],
                    "estado": e["estado"],
                    "concepto": e["concepto"],
                    "nivel": nivel,
                    "fuentes": [],
                },
            )
            par["fuentes"].append(f"{variante}#{fila['orden']}")
    for texto, concepto in DIFICILES:
        pares[texto] = {
            "texto": texto,
            "estado": "reconocido",
            "concepto": concepto,
            "nivel": "dificil",
            "fuentes": ["DIFICILES"],
        }
    return {
        "descripcion": (
            "Concepto que un humano espera para cada renglon. exacto y facil: el top-1 se exige; "
            "dificil: se reporta; hueco: no puede salir ningun producto y tiene que haber motivo; "
            "informativo: lo resuelve el parseo, no el catalogo."
        ),
        "catalogo": "datos/catalogo/conceptos.csv",
        "pares": list(pares.values()),
    }


def _json(objeto) -> bytes:
    return (json.dumps(objeto, ensure_ascii=False, indent=2) + "\n").encode()


def indice_adversarial() -> dict[str, str]:
    """Las entradas de los fixtures de la fase 5 (`ensayos/adversariales/fixtures/`).

    El indice es uno solo para las dos carpetas (`Tukit-QA/acuerdos.md` 1.3) y
    este script es su unico duenio: los fixtures ADV los escribe
    `ensayos/adversariales/construir.py`, y aqui solo se leen los ya versionados.
    """
    carpeta = RAIZ / "ensayos" / "adversariales" / "fixtures"
    entradas_adv: dict[str, str] = {}
    for ruta in sorted(carpeta.glob("ADV-*.json")):
        entradas_adv[json.loads(ruta.read_text())["sha256_pagina"]] = ruta.relative_to(RAIZ).as_posix()
    return entradas_adv


def archivos() -> dict[str, bytes]:
    """Todo lo que el script escribe, por ruta relativa a `datos/golden/`."""
    salida: dict[str, bytes] = {}
    indice: dict[str, str] = {}
    for variante, contenido in entradas().items():
        nombre, _ = VARIANTES[variante]
        salida[f"listas/{nombre}"] = contenido
        salida[f"esperado/{variante}.json"] = _json(esperado(variante))
        if variante == "G02":
            continue  # pasa el tope: ninguna pagina llega al modelo, no hay respuesta que grabar
        datos = fixture(variante, contenido)
        ruta = f"fixtures-modelo/{variante}-p1.json"
        salida[ruta] = _json(datos)
        indice[datos["sha256_pagina"]] = f"datos/golden/{ruta}"
    indice.update(indice_adversarial())
    salida["fixtures-modelo/indice.json"] = _json(dict(sorted(indice.items(), key=lambda par: par[1])))
    salida["esperado/oracle.json"] = _json(oraculo())
    return salida


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--comprobar", action="store_true", help="no escribe: compara con lo versionado")
    args = parser.parse_args(argv)
    distintos = []
    for ruta, contenido in archivos().items():
        destino = AQUI / ruta
        if args.comprobar:
            if not destino.exists() or destino.read_bytes() != contenido:
                distintos.append(ruta)
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
        print(f"{ruta}  {len(contenido)} bytes  {hashlib.sha256(contenido).hexdigest()[:12]}")
    if distintos:
        print("Distinto de lo versionado:", *distintos, sep="\n  ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
