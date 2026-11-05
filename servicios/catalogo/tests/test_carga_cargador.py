"""NFR-MAN-01: el cargador decide que entra a la base, que se rechaza y que se respeta.

`cargador` lleva los CSV curados a Postgres. Las piezas puras (ISBN, pesos a
centavos, referencias) ya estan fijadas en `test_cargador`; aqui se caracteriza lo
que decide sobre ficheros y sobre la base:

- **Armado en memoria.** Como se leen los CSV (booleanos, listas `a|b|c`, fechas
  con zona), que defaults se aplican, que filas se omiten con un problema
  BLOQUEANTE (precio no positivo, ISBN con digito de control malo, concepto o
  tienda desconocidos) y que una referencia rota detiene la carga entera antes de
  escribir una sola fila.
- **Libros.** La semilla desnormalizada (una fila = un libro en una tienda) se
  parte en producto + oferta + precio, el mismo ISBN en dos tiendas es UN
  producto con DOS ofertas, y dos niveles contradictorios para un ISBN se
  denuncian en vez de resolverse por el orden del fichero.
- **Idempotencia y respeto al enriquecimiento.** Cargar dos veces no duplica; la
  segunda carga actualiza lo que el CSV sabe y NO pisa lo que `enriquecer`
  averiguo despues (imagen, empaque, personaje, atributos, `admite_personaje`).
- **Orquestacion.** Un problema bloqueante devuelve 1 sin escribir; `--solo-validar`
  no toca la base.

La base es SQLite en un fichero de `tmp_path`, inyectada en lugar del motor de
Postgres; los CSV de entrada se escriben en `tmp_path`, nunca en `datos/`. Lo que
solo existe en Postgres (`FILTER`, `unnest`, `~*` de `medir_en_bd`) se prueba con
un motor falso que devuelve filas fijas: se afirma el mapeo, no el SQL.
"""

from __future__ import annotations

import csv
import json
import re
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from tukit_catalogo import cargador
from tukit_catalogo.cargador import (
    AGENTE_FIRECRAWL,
    Cargador,
    Informe,
    Problema,
    _bool,
    _fecha,
    _lista,
    _texto,
    _uuid_estable,
    leer_csv,
)
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
    Tienda,
)
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

CURADOR = uuid.UUID("00000000-0000-0000-0000-0000000000c1")
U_CUADERNO = uuid.UUID(int=0x101)
U_DICCIONARIO = uuid.UUID(int=0x102)
U_LAPIZ = uuid.UUID(int=0x103)
T_EXITO = uuid.UUID(int=0x201)
T_PANA = uuid.UUID(int=0x202)
P_CUADERNO = uuid.UUID(int=0x301)
P_LAPIZ = uuid.UUID(int=0x302)
O_CUADERNO = uuid.UUID(int=0x401)
O_LAPIZ = uuid.UUID(int=0x402)

ISBN_A = "9789580714729"
ISBN_B = "9788428536523"
ISBN_MALO = "9789580714728"  # mismo largo y prefijo, digito de control equivocado

COLUMNAS_CONCEPTO = [
    "id",
    "codigo",
    "nombre_canonico",
    "sinonimos",
    "categoria",
    "tipo_item",
    "atributos_discriminantes",
    "atributos_descriptivos",
    "admite_personaje",
    "frecuencia_demanda",
    "activo",
]
COLUMNAS_TIENDA = ["id", "slug", "nombre", "tipo", "url_base", "activa"]
COLUMNAS_PRODUCTO = [
    "id",
    "concepto_id",
    "ean",
    "sku_interno",
    "nombre",
    "descripcion",
    "marca",
    "nivel",
    "personaje",
    "imagen_url",
    "ruta_categoria",
    "es_propio",
    "es_representante_canonico",
    "activo",
    "unidad_base",
    "unidades_por_empaque",
    "quality_score",
    "curado_por",
]
COLUMNAS_OFERTA = [
    "id",
    "producto_canonico_id",
    "tienda_id",
    "referencia_externa",
    "url",
    "metodo_vinculacion",
    "confianza_vinculacion",
    "disponible",
    "activo",
]
COLUMNAS_PRECIO = ["id", "oferta_id", "valor_centavos", "moneda", "fuente", "vigente_desde"]
COLUMNAS_LIBRO = [
    "concepto_codigo",
    "titulo",
    "isbn13",
    "editorial",
    "nivel",
    "tienda_slug",
    "precio_cop",
    "imagen_url",
    "url_origen",
    "disponible",
    "sku_tienda",
    "observado_en",
]


# ---------------------------------------------------------------------------
# Ficheros de entrada
# ---------------------------------------------------------------------------


def _csv(directorio: Path, nombre: str, columnas: list[str], filas: list[dict[str, str]]) -> None:
    with (directorio / f"{nombre}.csv").open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=columnas)
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({**dict.fromkeys(columnas, ""), **fila})


def _libro(**kw: str) -> dict[str, str]:
    base = {
        "concepto_codigo": "dic-ingles",
        "titulo": "Diccionario Ficticio Ingles Espanol",
        "isbn13": ISBN_A,
        "editorial": "Editorial Ficticia",
        "nivel": "economico",
        "tienda_slug": "panamericana",
        "precio_cop": "8.400",
        "imagen_url": "",
        "url_origen": "https://panamericana.example.test/diccionario",
        "disponible": "true",
        "sku_tienda": "712417",
        "observado_en": "2026-09-21",
    }
    base.update(kw)
    return base


@pytest.fixture()
def datos(tmp_path: Path) -> Path:
    """Un directorio de CSV minimo y coherente; cada prueba lo ajusta."""
    carpeta = tmp_path / "csv"
    carpeta.mkdir()
    _csv(
        carpeta,
        "conceptos",
        COLUMNAS_CONCEPTO,
        [
            {
                "id": str(U_CUADERNO),
                "codigo": "C001",
                "nombre_canonico": "cuaderno",
                "sinonimos": "cuaderno cosido|cuaderno grande",
                "categoria": "escritura",
                "tipo_item": "util",
                "atributos_discriminantes": "hojas|rayado",
                "admite_personaje": "false",
                "frecuencia_demanda": "12",
            },
            {
                "id": str(U_DICCIONARIO),
                "codigo": "C034",
                "nombre_canonico": "diccionario",
                "tipo_item": "util",
                "frecuencia_demanda": "70",
            },
            {
                "id": str(U_LAPIZ),
                "codigo": "C002",
                "nombre_canonico": "lapiz",
                "admite_personaje": "si",
                "activo": "no",
            },
        ],
    )
    _csv(
        carpeta,
        "tiendas",
        COLUMNAS_TIENDA,
        [
            {
                "id": str(T_EXITO),
                "slug": "exito",
                "nombre": "Exito",
                "url_base": "https://exito.example.test",
            },
            {"id": str(T_PANA), "slug": "panamericana", "nombre": "Panamericana", "activa": "true"},
        ],
    )
    _csv(
        carpeta,
        "productos_canonicos",
        COLUMNAS_PRODUCTO,
        [
            {
                "id": str(P_CUADERNO),
                "concepto_id": str(U_CUADERNO),
                "ean": "770-1234-567890",
                "sku_interno": "TK-C001-A",
                "nombre": "Cuaderno Ficticio",
                "marca": "Marca Ficticia",
                "imagen_url": "https://img.example.test/c.jpg",
                "curado_por": str(CURADOR),
            },
            {
                "id": str(P_LAPIZ),
                "concepto_id": str(U_LAPIZ),
                "sku_interno": "TK-C002-A",
                "nombre": "Lapiz Ficticio",
                "nivel": "premium",
                "unidades_por_empaque": "12",
                "quality_score": "0.95",
                "activo": "false",
                "curado_por": str(CURADOR),
            },
        ],
    )
    _csv(
        carpeta,
        "ofertas_tienda",
        COLUMNAS_OFERTA,
        [
            {
                "id": str(O_CUADERNO),
                "producto_canonico_id": str(P_CUADERNO),
                "tienda_id": str(T_EXITO),
                "referencia_externa": "R-1",
                "url": "https://exito.example.test/c/p",
                "disponible": "",
            },
            {
                "id": str(O_LAPIZ),
                "producto_canonico_id": str(P_LAPIZ),
                "tienda_id": str(T_PANA),
                "referencia_externa": "R-2",
                "metodo_vinculacion": "atributos",
                "confianza_vinculacion": "0.855",
                "disponible": "false",
                "activo": "false",
            },
        ],
    )
    _csv(
        carpeta,
        "precios_oferta",
        COLUMNAS_PRECIO,
        [
            {
                "id": str(uuid.UUID(int=0x501)),
                "oferta_id": str(O_CUADERNO),
                "valor_centavos": "650000",
                "vigente_desde": "2026-09-02T00:00:00",
            },
            {
                "id": str(uuid.UUID(int=0x502)),
                "oferta_id": str(O_LAPIZ),
                "valor_centavos": "120000",
                "moneda": "COP",
                "fuente": "manual",
                "vigente_desde": "2026-09-02T00:00:00-05:00",
            },
        ],
    )
    return carpeta


def _conceptos_por_codigo(armado: dict) -> dict[str, dict]:
    return {c["codigo"]: c for c in armado["concepto"]}


# ---------------------------------------------------------------------------
# Lectura de los CSV
# ---------------------------------------------------------------------------


class TestLecturaTolerante:
    """Los CSV los escribe gente: el lector acepta variantes y no inventa."""

    @pytest.mark.parametrize("crudo", ["true", "TRUE", " Si ", "1", "t", "yes", "Verdadero"])
    def test_las_formas_de_decir_si(self, crudo):
        assert _bool(crudo) is True

    @pytest.mark.parametrize("crudo", ["false", "no", "0", "nunca", "x"])
    def test_cualquier_otra_cosa_es_no(self, crudo):
        assert _bool(crudo, por_omision=True) is False

    @pytest.mark.parametrize("vacio", [None, "", "   "])
    def test_lo_vacio_toma_el_valor_por_omision(self, vacio):
        assert _bool(vacio) is False
        assert _bool(vacio, por_omision=True) is True

    def test_texto_recorta_y_convierte_lo_vacio_en_none(self):
        assert _texto("  hola ") == "hola"
        assert _texto("   ") is None
        assert _texto(None) is None

    @pytest.mark.parametrize(
        ("crudo", "esperado"),
        [
            ("a|b|c", ["a", "b", "c"]),
            ("a, b ,c", ["a", "b", "c"]),
            ("uno solo", ["uno solo"]),
            ('["x", "y"]', ["x", "y"]),
            ("[1, 2]", ["1", "2"]),
            ("[]", []),
            ("{}", []),
            ("", []),
            (None, []),
            ("[esto no es json", []),  # un JSON roto no revienta la carga
            ('{"a": 1}'.replace("{", "["), []),  # lo que parece lista pero no es JSON valido
            ("a||b|", ["a", "b"]),
        ],
    )
    def test_listas_en_los_dos_formatos(self, crudo, esperado):
        assert _lista(crudo) == esperado

    def test_fecha_ingenua_se_interpreta_en_utc_y_la_con_zona_se_respeta(self):
        ingenua = _fecha("2026-09-02T08:00:00")
        assert ingenua == datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
        con_zona = _fecha("2026-09-02T08:00:00-05:00")
        assert con_zona.utcoffset().total_seconds() == -5 * 3600
        assert con_zona == datetime(2026, 9, 2, 13, 0, tzinfo=UTC)

    @pytest.mark.parametrize("malo", ["", None, "ayer", "2026-13-45"])
    def test_fecha_ausente_o_invalida_cae_a_ahora_con_zona(self, malo):
        antes = datetime.now(UTC)
        valor = _fecha(malo)
        assert valor.tzinfo is not None
        assert antes <= valor <= datetime.now(UTC)

    def test_un_fichero_que_no_existe_es_una_lista_vacia(self, tmp_path):
        assert leer_csv(tmp_path / "no_existe.csv") == []

    def test_el_uuid_estable_depende_solo_del_contenido(self):
        assert _uuid_estable("libro", ISBN_A) == _uuid_estable("libro", ISBN_A)
        assert _uuid_estable("libro", ISBN_A) != _uuid_estable("libro", ISBN_B)
        assert _uuid_estable("oferta", ISBN_A, "exito") != _uuid_estable("oferta", ISBN_A, "pana")


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------


class TestInforme:
    def test_el_problema_dice_si_bloquea(self):
        assert str(Problema(True, "isbn", "x")) == "[BLOQUEA] isbn: x"
        assert str(Problema(False, "imagen", "y")) == "[carencia] imagen: y"

    def test_solo_un_problema_bloqueante_bloquea(self):
        sin = Informe({}, [Problema(False, "imagen", "falta")], {})
        con = Informe({}, [Problema(False, "imagen", "falta"), Problema(True, "isbn", "malo")], {})
        assert sin.bloqueado is False
        assert con.bloqueado is True

    def test_imprime_lo_cargado_las_carencias_y_los_bloqueos(self, capsys):
        informe = Informe(
            escritos={"producto_canonico": 3},
            problemas=[Problema(True, "precio", "oferta X: '0'")],
            carencias={"productos sin imagen": (1, 4)},
        )
        informe.imprimir()
        salida = capsys.readouterr().out
        assert "producto_canonico" in salida
        assert "1 problema(s) que BLOQUEAN" in salida
        assert "[BLOQUEA] precio: oferta X: '0'" in salida
        assert "productos sin imagen" in salida
        assert "(25%)" in salida

    def test_recorta_la_lista_de_bloqueos_para_no_inundar_la_consola(self, capsys):
        problemas = [Problema(True, "isbn", f"fila {i}") for i in range(25)]
        Informe({}, problemas, {}).imprimir()
        salida = capsys.readouterr().out
        assert "fila 19" in salida
        assert "fila 20" not in salida
        assert "... y 5 mas" in salida

    def test_recorta_las_carencias_con_nombre_propio_a_quince(self, capsys):
        problemas = [Problema(False, "imagen", f"carencia {i}") for i in range(17)]
        Informe({}, problemas, {}).imprimir()
        salida = capsys.readouterr().out
        assert "17 carencia(s) con nombre propio" in salida
        assert "carencia 14" in salida
        assert "carencia 15" not in salida
        assert "... y 2 mas" in salida

    def test_una_carencia_sobre_cero_total_no_divide_por_cero(self, capsys):
        Informe({}, [], {"conceptos sin ningun producto": (0, 0)}).imprimir()
        assert "(0%)" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Armado en memoria
# ---------------------------------------------------------------------------


class TestArmadoDeConceptosYTiendas:
    def test_los_conceptos_traen_sus_valores_y_defaults(self, datos):
        armado = Cargador(datos).armar()
        conceptos = _conceptos_por_codigo(armado)
        cuaderno = conceptos["C001"]
        assert cuaderno["id"] == U_CUADERNO
        assert cuaderno["sinonimos"] == ["cuaderno cosido", "cuaderno grande"]
        assert cuaderno["atributos_discriminantes"] == ["hojas", "rayado"]
        assert cuaderno["atributos_descriptivos"] == []
        assert cuaderno["admite_personaje"] is False
        assert cuaderno["frecuencia_demanda"] == 12
        assert cuaderno["activo"] is True  # vacio -> activo
        diccionario = conceptos["C034"]
        assert diccionario["categoria"] == "otro"  # sin categoria
        lapiz = conceptos["C002"]
        assert lapiz["admite_personaje"] is True
        assert lapiz["activo"] is False

    def test_agrega_las_librerias_de_la_semilla_que_faltan_sin_duplicar_las_que_hay(self, datos):
        tiendas = Cargador(datos).armar()["tienda"]
        slugs = [t["slug"] for t in tiendas]
        assert sorted(slugs) == sorted(
            ["exito", "panamericana", "librerianacional", "buscalibre", "tirant", "edileyer"]
        )
        assert slugs.count("panamericana") == 1
        agregada = next(t for t in tiendas if t["slug"] == "tirant")
        assert agregada["id"] == _uuid_estable("tienda", "tirant")  # estable entre corridas
        assert agregada["tipo"] == "minorista"
        assert agregada["activa"] is True
        # La que venia en el CSV conserva su id y sus datos.
        pana = next(t for t in tiendas if t["slug"] == "panamericana")
        assert pana["id"] == T_PANA
        exito = next(t for t in tiendas if t["slug"] == "exito")
        assert exito["url_base"] == "https://exito.example.test"
        assert pana["url_base"] is None


class TestArmadoDeProductosOfertasYPrecios:
    def test_un_producto_toma_defaults_y_normaliza_el_ean(self, datos):
        productos = {p["sku_interno"]: p for p in Cargador(datos).armar()["producto_canonico"]}
        cuaderno = productos["TK-C001-A"]
        assert cuaderno["ean"] == "7701234567890"  # solo digitos
        assert cuaderno["nivel"] == "confiable"
        assert cuaderno["unidad_base"] == "unidad"
        assert cuaderno["unidades_por_empaque"] == 1
        assert cuaderno["quality_score"] == 0.7
        assert cuaderno["atributos"] == {}  # los atributos reales los siembra `enriquecer`
        assert cuaderno["activo"] is True
        assert cuaderno["curado_por"] == CURADOR
        assert cuaderno["descripcion"] is None
        lapiz = productos["TK-C002-A"]
        assert lapiz["ean"] is None
        assert lapiz["nivel"] == "premium"
        assert lapiz["unidades_por_empaque"] == 12
        assert lapiz["quality_score"] == 0.95
        assert lapiz["activo"] is False

    def test_una_oferta_toma_defaults_y_respeta_lo_que_trae(self, datos):
        ofertas = {o["id"]: o for o in Cargador(datos).armar()["oferta_tienda"]}
        cuaderno = ofertas[O_CUADERNO]
        assert cuaderno["metodo_vinculacion"] == "manual"
        assert cuaderno["confianza_vinculacion"] == 1.0
        assert cuaderno["disponible"] is True  # sin dato, disponible
        assert cuaderno["activo"] is True
        lapiz = ofertas[O_LAPIZ]
        assert lapiz["metodo_vinculacion"] == "atributos"
        assert lapiz["confianza_vinculacion"] == 0.855
        assert lapiz["disponible"] is False
        assert lapiz["activo"] is False

    def test_el_precio_exige_zona_horaria_y_defaults_de_moneda_y_fuente(self, datos):
        precios = {p["oferta_id"]: p for p in Cargador(datos).armar()["precio_oferta"]}
        sin_zona = precios[O_CUADERNO]
        assert sin_zona["valor_centavos"] == 650000
        assert sin_zona["moneda"] == "COP"
        assert sin_zona["fuente"] == "scraper"
        assert sin_zona["vigente_desde"] == datetime(2026, 9, 2, tzinfo=UTC)  # ingenua -> UTC
        con_zona = precios[O_LAPIZ]
        assert con_zona["fuente"] == "manual"
        assert con_zona["vigente_desde"] == datetime(2026, 9, 2, 5, 0, tzinfo=UTC)

    @pytest.mark.parametrize("valor", ["0", "-500", "abc", ""])
    def test_un_precio_no_positivo_o_ilegible_bloquea_y_no_se_carga(self, datos, valor):
        """Un precio de cero se propaga al total del kit como si el producto fuera gratis."""
        _csv(
            datos,
            "precios_oferta",
            COLUMNAS_PRECIO,
            [
                {"id": str(uuid.UUID(int=0x501)), "oferta_id": str(O_CUADERNO), "valor_centavos": "650000"},
                {"id": str(uuid.UUID(int=0x503)), "oferta_id": str(O_LAPIZ), "valor_centavos": valor},
            ],
        )
        cargador_ = Cargador(datos)
        armado = cargador_.armar()
        assert [p["oferta_id"] for p in armado["precio_oferta"]] == [O_CUADERNO]  # el malo se omitio
        bloqueantes = [p for p in cargador_.problemas if p.bloqueante]
        assert [p.clase for p in bloqueantes] == ["precio"]
        assert str(O_LAPIZ) in bloqueantes[0].detalle

    def test_un_precio_sin_la_columna_valor_tambien_bloquea(self, datos):
        _csv(
            datos,
            "precios_oferta",
            ["id", "oferta_id"],
            [{"id": str(uuid.UUID(int=0x503)), "oferta_id": str(O_LAPIZ)}],
        )
        cargador_ = Cargador(datos)
        assert cargador_.armar()["precio_oferta"] == []
        assert [p.clase for p in cargador_.problemas if p.bloqueante] == ["precio"]

    def test_una_oferta_huerfana_se_denuncia_por_cada_referencia_rota(self, datos):
        """Postgres diria el nombre de la restriccion; aqui se dice en que fila esta el error."""
        huerfana = uuid.UUID(int=0x999)
        _csv(
            datos,
            "ofertas_tienda",
            COLUMNAS_OFERTA,
            [
                {
                    "id": str(O_CUADERNO),
                    "producto_canonico_id": str(huerfana),
                    "tienda_id": str(uuid.UUID(int=0x998)),
                    "referencia_externa": "R-1",
                }
            ],
        )
        cargador_ = Cargador(datos)
        cargador_.armar()
        detalles = sorted(p.detalle for p in cargador_.problemas if p.clase == "referencia" and p.bloqueante)
        # La oferta rota apunta a producto y tienda inexistentes; ademas, el precio
        # de la oferta lapiz (que ya no esta) cuelga de nada. Se listan TODOS.
        assert any(f"-> producto {huerfana}" in d for d in detalles)
        assert any("-> tienda" in d for d in detalles)
        assert any(f"-> oferta {O_LAPIZ}" in d for d in detalles)

    def test_un_producto_con_concepto_inexistente_bloquea(self, datos):
        _csv(
            datos,
            "productos_canonicos",
            COLUMNAS_PRODUCTO,
            [
                {
                    "id": str(P_CUADERNO),
                    "concepto_id": str(uuid.UUID(int=0x777)),
                    "sku_interno": "TK-X",
                    "nombre": "Huerfano Ficticio",
                    "curado_por": str(CURADOR),
                }
            ],
        )
        cargador_ = Cargador(datos)
        cargador_.armar()
        assert any(
            p.bloqueante and p.clase == "referencia" and "-> concepto" in p.detalle
            for p in cargador_.problemas
        )

    def test_un_directorio_sin_ficheros_arma_lo_unico_que_trae_de_fabrica(self, tmp_path):
        armado = Cargador(tmp_path).armar()
        assert armado["concepto"] == []
        assert armado["producto_canonico"] == []
        assert armado["oferta_tienda"] == []
        assert armado["precio_oferta"] == []
        assert len(armado["tienda"]) == 5  # las cinco librerias de la semilla de libros

    def test_mide_las_carencias_sobre_lo_armado(self, datos):
        cargador_ = Cargador(datos)
        cargador_.armar()
        carencias = cargador_.carencias
        # Un producto con imagen y otro sin ella.
        assert carencias["productos sin imagen"] == (1, 2)
        assert carencias["productos sin atributos"] == (2, 2)
        assert carencias["productos sin marca"] == (1, 2)
        assert carencias["productos con empaque asumido en 1"] == (1, 2)
        # C001 y C002 tienen producto; C034 no.
        assert carencias["conceptos sin ningun producto"] == (1, 3)
        assert carencias["conceptos sin los 3 niveles"] == (3, 3)
        assert carencias["ofertas sin enlace a la tienda"] == (1, 2)


# ---------------------------------------------------------------------------
# Libros
# ---------------------------------------------------------------------------


class TestArmadoDeLibros:
    def _con_libros(self, datos: Path, filas: list[dict[str, str]]) -> Cargador:
        _csv(datos, "libros_firecrawl", COLUMNAS_LIBRO, filas)
        cargador_ = Cargador(datos)
        self.armado = cargador_.armar()
        return cargador_

    def test_un_libro_se_parte_en_producto_oferta_y_precio(self, datos):
        c = self._con_libros(datos, [_libro(isbn13="978-958-07-1472-9")])  # con guiones
        libros = [p for p in self.armado["producto_canonico"] if p["sku_interno"].startswith("TK-LIB-")]
        assert [p["sku_interno"] for p in libros] == [f"TK-LIB-{ISBN_A}"]
        libro = libros[0]
        assert libro["id"] == _uuid_estable("libro", ISBN_A)
        assert libro["ean"] == ISBN_A
        assert libro["nombre"] == "Diccionario Ficticio Ingles Espanol"
        assert libro["marca"] == "Editorial Ficticia"
        assert libro["nivel"] == "economico"
        assert libro["atributos"] == {"isbn13": ISBN_A}
        assert libro["quality_score"] == 0.9
        assert libro["curado_por"] == AGENTE_FIRECRAWL  # lo trajo un agente, no una persona
        assert libro["unidades_por_empaque"] == 1
        assert not [p for p in c.problemas if p.bloqueante]
        oferta = next(o for o in self.armado["oferta_tienda"] if o["producto_canonico_id"] == libro["id"])
        assert oferta["referencia_externa"] == "712417"
        assert oferta["metodo_vinculacion"] == "ean"
        assert oferta["confianza_vinculacion"] == 1.0
        assert oferta["tienda_id"] == T_PANA
        precio = next(p for p in self.armado["precio_oferta"] if p["oferta_id"] == oferta["id"])
        assert precio["valor_centavos"] == 840000  # 8.400 pesos: el punto es de miles
        assert precio["fuente"] == "scraper"
        assert precio["vigente_desde"] == datetime(2026, 9, 21, tzinfo=UTC)

    def test_el_mismo_isbn_en_dos_tiendas_es_un_producto_con_dos_ofertas(self, datos):
        """El caso que el modelo plano no podia expresar: un libro, dos precios."""
        self._con_libros(
            datos,
            [
                _libro(tienda_slug="panamericana", precio_cop="153.000", sku_tienda="A1"),
                _libro(
                    tienda_slug="buscalibre",
                    precio_cop="130.812",
                    sku_tienda="B1",
                    imagen_url="https://img.example.test/p.jpg",
                ),
            ],
        )
        libros = [p for p in self.armado["producto_canonico"] if p["sku_interno"].startswith("TK-LIB-")]
        assert len(libros) == 1
        # La primera fila no traia portada y la segunda si: se queda la que exista.
        assert libros[0]["imagen_url"] == "https://img.example.test/p.jpg"
        ofertas = [o for o in self.armado["oferta_tienda"] if o["producto_canonico_id"] == libros[0]["id"]]
        assert sorted(o["referencia_externa"] for o in ofertas) == ["A1", "B1"]
        valores = sorted(
            p["valor_centavos"]
            for p in self.armado["precio_oferta"]
            if p["oferta_id"] in {o["id"] for o in ofertas}
        )
        assert valores == [13081200, 15300000]

    def test_sin_sku_de_tienda_la_referencia_es_el_isbn(self, datos):
        self._con_libros(datos, [_libro(sku_tienda="")])
        oferta = next(
            o
            for o in self.armado["oferta_tienda"]
            if o["producto_canonico_id"] == _uuid_estable("libro", ISBN_A)
        )
        assert oferta["referencia_externa"] == ISBN_A

    def test_los_ids_de_los_libros_no_cambian_entre_corridas(self, datos):
        """Es lo que vuelve repetible la carga: la segunda corrida actualiza, no duplica."""
        filas = [_libro(), _libro(isbn13=ISBN_B, titulo="Otro Libro Ficticio", tienda_slug="exito")]
        self._con_libros(datos, filas)
        primero = {
            tabla: sorted(str(f["id"]) for f in self.armado[tabla])
            for tabla in ("producto_canonico", "oferta_tienda", "precio_oferta")
        }
        Cargador(datos).armar()
        segundo = Cargador(datos).armar()
        assert primero == {
            tabla: sorted(str(f["id"]) for f in segundo[tabla])
            for tabla in ("producto_canonico", "oferta_tienda", "precio_oferta")
        }

    def test_un_concepto_de_libro_que_ya_existe_conserva_id_y_demanda_y_pasa_a_libro_libre(self, datos):
        """C034 ya era el diccionario de papeleria: se engancha a ESE, no se duplica."""
        self._con_libros(
            datos, [_libro(concepto_codigo="C034", isbn13=ISBN_B, titulo="Diccionario Ficticio")]
        )
        c034 = _conceptos_por_codigo(self.armado)["C034"]
        assert c034["id"] == U_DICCIONARIO
        assert c034["frecuencia_demanda"] == 70
        assert c034["tipo_item"] == "libro_libre"
        assert [c["codigo"] for c in self.armado["concepto"]].count("C034") == 1
        libro = next(p for p in self.armado["producto_canonico"] if p["sku_interno"] == f"TK-LIB-{ISBN_B}")
        assert libro["concepto_id"] == U_DICCIONARIO

    def test_una_fila_vieja_de_dic_ingles_se_cuelga_del_diccionario_c034(self, datos):
        """`dic-ingles` ya no nace: se lee como C034 (`CONCEPTOS_LIBRO_FUSIONADOS`, cargador.py:350).

        Antes era un concepto nuevo `libro_libre` con la demanda de la semilla. oe5 lo fundio en
        C034, que filtra por `idioma`: partido, el mismo diccionario salia curado en un grado y
        como hueco en otro.
        """
        self._con_libros(
            datos,
            [_libro(), _libro(isbn13=ISBN_B, titulo="Otro Diccionario Ficticio", tienda_slug="exito")],
        )
        conceptos = _conceptos_por_codigo(self.armado)
        assert "dic-ingles" not in conceptos
        assert conceptos["C034"]["id"] == U_DICCIONARIO
        assert conceptos["C034"]["tipo_item"] == "libro_libre"  # sin esto el pipeline le buscaria papeleria
        libros = [p for p in self.armado["producto_canonico"] if p["sku_interno"].startswith("TK-LIB-")]
        assert {p["sku_interno"] for p in libros} == {f"TK-LIB-{ISBN_A}", f"TK-LIB-{ISBN_B}"}
        assert {p["concepto_id"] for p in libros} == {U_DICCIONARIO}

    def test_los_conceptos_de_libro_que_nadie_pidio_no_se_crean(self, datos):
        self._con_libros(datos, [_libro()])
        codigos = set(_conceptos_por_codigo(self.armado))
        assert "dic-ingles" not in codigos  # se lee como C034 (cargador.py:350)
        assert "C034" in codigos
        assert "C048" in codigos  # la biblia nace aunque la semilla actual no traiga una
        assert "C042" in codigos

    def test_un_isbn_con_digito_de_control_malo_se_omite_y_bloquea(self, datos):
        """Una pagina de categoria raspada como ficha traeria un 'ISBN' que no lo es."""
        c = self._con_libros(datos, [_libro(isbn13=ISBN_MALO, titulo="Falso"), _libro(isbn13="732461")])
        assert not [p for p in self.armado["producto_canonico"] if p["sku_interno"].startswith("TK-LIB-")]
        isbn_problemas = [p for p in c.problemas if p.clase == "isbn"]
        assert len(isbn_problemas) == 2
        assert all(p.bloqueante for p in isbn_problemas)
        assert "fila 2 de libros_firecrawl.csv" in isbn_problemas[0].detalle
        assert "fila 3 de libros_firecrawl.csv" in isbn_problemas[1].detalle

    def test_un_concepto_desconocido_se_omite_y_bloquea(self, datos):
        c = self._con_libros(datos, [_libro(concepto_codigo="C999")])
        assert not [p for p in self.armado["producto_canonico"] if p["sku_interno"].startswith("TK-LIB-")]
        assert [(p.clase, p.bloqueante) for p in c.problemas if p.clase == "concepto"] == [("concepto", True)]
        assert "C999" in next(p.detalle for p in c.problemas if p.clase == "concepto")

    def test_una_tienda_desconocida_se_omite_y_bloquea(self, datos):
        c = self._con_libros(datos, [_libro(tienda_slug="libreria-que-no-existe")])
        assert not [o for o in self.armado["oferta_tienda"] if o["referencia_externa"] == "712417"]
        problema = next(p for p in c.problemas if p.clase == "tienda")
        assert problema.bloqueante
        assert "libreria-que-no-existe" in problema.detalle

    def test_un_precio_ilegible_bloquea_con_el_titulo_en_el_detalle(self, datos):
        c = self._con_libros(datos, [_libro(precio_cop="gratis")])
        problema = next(p for p in c.problemas if p.clase == "precio")
        assert problema.bloqueante
        assert "Diccionario Ficticio Ingles Espanol" in problema.detalle
        assert not self.armado["precio_oferta"] or all(
            p["oferta_id"] != _uuid_estable("oferta", ISBN_A, "panamericana")
            for p in self.armado["precio_oferta"]
        )

    def test_dos_niveles_para_el_mismo_isbn_se_denuncian_en_vez_de_elegir_por_el_orden(self, datos):
        """El nivel es del PRODUCTO: la biblia quedo 'confiable' por la fila que se leyo primero."""
        c = self._con_libros(
            datos,
            [
                _libro(tienda_slug="panamericana", nivel="confiable"),
                _libro(tienda_slug="buscalibre", nivel="premium"),
            ],
        )
        problemas = [p for p in c.problemas if p.clase == "nivel"]
        assert len(problemas) == 1
        assert problemas[0].bloqueante
        assert ISBN_A in problemas[0].detalle
        assert "['confiable', 'premium']" in problemas[0].detalle
        assert Informe({}, c.problemas, {}).bloqueado

    def test_el_mismo_nivel_en_dos_tiendas_no_es_un_conflicto(self, datos):
        c = self._con_libros(
            datos,
            [_libro(tienda_slug="panamericana"), _libro(tienda_slug="buscalibre", sku_tienda="B")],
        )
        assert not [p for p in c.problemas if p.clase == "nivel"]

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-09: el mismo ISBN repetido para la misma tienda arma dos ofertas con el mismo "
            "id en un solo INSERT ... ON CONFLICT DO UPDATE (Postgres lo rechaza) sin denunciarlo"
        ),
    )
    def test_el_mismo_isbn_repetido_en_una_tienda_no_genera_filas_con_el_mismo_id(self, datos):
        """Una re-observacion del mismo libro en la misma tienda no puede llegar duplicada a la base.

        Correcto: o se consolida en una sola oferta/precio, o se denuncia con un
        problema bloqueante. Hoy `_libros` agrega una oferta por fila (cargador.py,
        bucle `for i, f in enumerate(filas)`) con id derivado de (isbn, tienda): dos
        filas iguales dan dos ofertas con el MISMO id, y Postgres aborta un
        `INSERT ... ON CONFLICT DO UPDATE` que toca la misma fila dos veces.
        """
        c = self._con_libros(
            datos,
            [
                _libro(precio_cop="8.400", observado_en="2026-09-01"),
                _libro(precio_cop="8.900", observado_en="2026-09-21"),
            ],
        )
        ofertas = [o["id"] for o in self.armado["oferta_tienda"]]
        precios = [p["id"] for p in self.armado["precio_oferta"]]
        hay_duplicados = len(ofertas) != len(set(ofertas)) or len(precios) != len(set(precios))
        assert not hay_duplicados or any(p.bloqueante for p in c.problemas)


# ---------------------------------------------------------------------------
# Escritura contra una base real (SQLite)
# ---------------------------------------------------------------------------


def _activar_fk(conexion, _registro):  # noqa: ANN001
    conexion.execute("PRAGMA foreign_keys=ON")


# Desde 6c29c83 la segunda carga COMBINA `atributos` con `||` (cargador.py:865-872),
# que en Postgres es la fusion de jsonb: las claves del CSV ganan y las demas se
# conservan. En SQLite `||` concatena texto y deja `{}{}`, que ya no es JSON. Para
# seguir probando la escritura sin una base real, el motor de prueba traduce esa
# fusion a una funcion con la misma regla que el `jsonb || jsonb` de objetos.
_FUSION_ATRIBUTOS = re.compile(r"\(producto_canonico\.atributos \|\| excluded\.atributos\)")
_FUSION_EN_SQLITE = "fusion_jsonb(producto_canonico.atributos, excluded.atributos)"


def _fusion_jsonb(base: str | None, nuevo: str | None) -> str:
    return json.dumps({**json.loads(base or "{}"), **json.loads(nuevo or "{}")})


def _activar_fusion_jsonb(conexion, _registro):  # noqa: ANN001
    conexion.create_function("fusion_jsonb", 2, _fusion_jsonb)


# Desde 02d8f24 el upsert ya no fusiona: `coalesce(nullif(excluded.atributos, '{}'::jsonb), ...)`
# (cargador.py:895). El cast es de Postgres; en SQLite el JSON es texto y `'{}'` es el vacio.
_VACIO_JSONB = "'{}'::jsonb"


def _traducir_fusion(_conexion, _cursor, sql, parametros, _contexto, _varios):  # noqa: ANN001
    return _FUSION_ATRIBUTOS.sub(_FUSION_EN_SQLITE, sql).replace(_VACIO_JSONB, "'{}'"), parametros


@pytest.fixture()
def bd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Sesion sincrona para consultar, y `crear_motor` apuntando al mismo fichero."""
    archivo = tmp_path / "catalogo.db"
    sincrono = create_engine(f"sqlite:///{archivo}")
    event.listen(sincrono, "connect", _activar_fk)
    Base.metadata.create_all(sincrono)

    def fabricar(servicio: str, *, echo: bool = False) -> MotorServicio:
        motor = create_async_engine(f"sqlite+aiosqlite:///{archivo}")
        event.listen(motor.sync_engine, "connect", _activar_fk)
        event.listen(motor.sync_engine, "connect", _activar_fusion_jsonb)
        event.listen(motor.sync_engine, "before_cursor_execute", _traducir_fusion, retval=True)
        return MotorServicio(servicio, motor, async_sessionmaker(motor, expire_on_commit=False))

    monkeypatch.setattr("tukit_comun.bd.crear_motor", fabricar)
    with Session(sincrono) as sesion:
        yield sesion
    sincrono.dispose()


def _contar(bd: Session) -> dict[str, int]:
    bd.rollback()
    return {
        modelo.__tablename__: bd.scalar(select(func.count()).select_from(modelo))
        for modelo in (Tienda, Concepto, ProductoCanonico, OfertaTienda, PrecioOferta)
    }


class TestEscrituraIdempotente:
    async def test_escribe_en_el_orden_de_las_dependencias_y_cuenta_lo_escrito(self, datos, bd):
        c = Cargador(datos)
        escritos = await c.escribir(c.armar())
        assert escritos == {
            "tienda": 6,
            "concepto": 3,
            "producto_canonico": 2,
            "oferta_tienda": 2,
            "precio_oferta": 2,
        }
        assert _contar(bd) == {
            "tienda": 6,
            "concepto": 3,
            "producto_canonico": 2,
            "oferta_tienda": 2,
            "precio_oferta": 2,
        }
        precio = bd.scalar(select(PrecioOferta).where(PrecioOferta.oferta_id == O_CUADERNO))
        assert precio.valor_centavos == 650000

    async def test_las_tablas_sin_filas_cuentan_cero_y_no_fallan(self, tmp_path, bd):
        c = Cargador(tmp_path)  # directorio vacio: solo las librerias de fabrica
        escritos = await c.escribir(c.armar())
        assert escritos == {
            "tienda": 5,
            "concepto": 0,
            "producto_canonico": 0,
            "oferta_tienda": 0,
            "precio_oferta": 0,
        }

    async def test_cargar_dos_veces_deja_la_misma_base(self, datos, bd):
        _csv(
            datos,
            "libros_firecrawl",
            COLUMNAS_LIBRO,
            [_libro(), _libro(tienda_slug="buscalibre", sku_tienda="B")],
        )
        primero = Cargador(datos)
        await primero.escribir(primero.armar())
        despues_de_una = _contar(bd)
        ids = set(bd.scalars(select(ProductoCanonico.id)))

        segundo = Cargador(datos)
        await segundo.escribir(segundo.armar())

        assert _contar(bd) == despues_de_una
        assert set(bd.scalars(select(ProductoCanonico.id))) == ids
        assert despues_de_una["producto_canonico"] == 3  # 2 de papeleria + 1 libro con 2 ofertas
        assert despues_de_una["oferta_tienda"] == 4

    async def test_la_segunda_carga_actualiza_lo_que_el_csv_sabe(self, datos, bd):
        c = Cargador(datos)
        await c.escribir(c.armar())

        filas = leer_csv(datos / "productos_canonicos.csv")
        filas[0]["nombre"] = "Cuaderno Ficticio Corregido"
        filas[0]["marca"] = "Otra Marca Ficticia"
        _csv(datos, "productos_canonicos", COLUMNAS_PRODUCTO, filas)
        precios = leer_csv(datos / "precios_oferta.csv")
        precios[0]["valor_centavos"] = "700000"
        _csv(datos, "precios_oferta", COLUMNAS_PRECIO, precios)
        c2 = Cargador(datos)
        await c2.escribir(c2.armar())

        bd.rollback()
        producto = bd.get(ProductoCanonico, P_CUADERNO)
        assert producto.nombre == "Cuaderno Ficticio Corregido"
        assert producto.marca == "Otra Marca Ficticia"
        precio = bd.scalar(select(PrecioOferta).where(PrecioOferta.oferta_id == O_CUADERNO))
        assert precio.valor_centavos == 700000
        assert _contar(bd)["precio_oferta"] == 2  # actualizo en sitio, no agrego un precio

    async def test_la_segunda_carga_no_deshace_el_enriquecimiento(self, datos, bd):
        """El cargador informaba 330 productos escritos y a la vez borraba las portadas.

        Desde 02d8f24 (`volcar` exporta lo que la base sabe) el CSV trae el producto
        completo y manda donde trae dato (cargador.py:886-915): la portada si viene, el
        personaje siempre (vacio es una decision) y el empaque si el CSV tiene la columna.
        Lo que el CSV deja vacio no pisa: una portada sin URL y los atributos `{}`.
        """
        c = Cargador(datos)
        await c.escribir(c.armar())

        bd.execute(
            update(ProductoCanonico)
            .where(ProductoCanonico.id == P_CUADERNO)
            .values(
                imagen_url="https://img.example.test/enriquecida.jpg",
                unidades_por_empaque=6,
                unidad_base="hoja",
                personaje="Personaje Ficticio",
                atributos={"hojas": 100},
            )
        )
        bd.commit()

        c2 = Cargador(datos)
        await c2.escribir(c2.armar())

        bd.rollback()
        producto = bd.get(ProductoCanonico, P_CUADERNO)
        bd.refresh(producto)
        assert producto.imagen_url == "https://img.example.test/c.jpg"  # el CSV la trae: manda
        assert producto.unidades_por_empaque == 1  # el CSV tiene la columna: manda
        assert producto.unidad_base == "unidad"
        assert producto.personaje is None  # vacio en el CSV es una decision
        assert producto.atributos == {"hojas": 100}  # `{}` en el CSV no dice nada

        bd.execute(
            update(ProductoCanonico)
            .where(ProductoCanonico.id == P_CUADERNO)
            .values(imagen_url="https://img.example.test/enriquecida.jpg")
        )
        bd.commit()
        filas = leer_csv(datos / "productos_canonicos.csv")
        for f in filas:
            f["imagen_url"] = ""
        _csv(datos, "productos_canonicos", COLUMNAS_PRODUCTO, filas)
        c3 = Cargador(datos)
        await c3.escribir(c3.armar())

        bd.rollback()
        producto = bd.get(ProductoCanonico, P_CUADERNO)
        bd.refresh(producto)
        assert producto.imagen_url == "https://img.example.test/enriquecida.jpg"  # sin URL no pisa

    async def test_admite_personaje_se_deduce_y_el_csv_no_lo_pisa(self, datos, bd):
        """El CSV decia que 7 conceptos admitian personaje; el catalogo ya tenia mas."""
        c = Cargador(datos)
        await c.escribir(c.armar())
        bd.execute(update(Concepto).where(Concepto.id == U_CUADERNO).values(admite_personaje=True))
        bd.execute(update(Concepto).where(Concepto.id == U_LAPIZ).values(admite_personaje=False))
        bd.commit()

        filas = leer_csv(datos / "conceptos.csv")
        filas[0]["nombre_canonico"] = "cuaderno renombrado"
        _csv(datos, "conceptos", COLUMNAS_CONCEPTO, filas)
        c2 = Cargador(datos)
        await c2.escribir(c2.armar())

        bd.rollback()
        cuaderno = bd.get(Concepto, U_CUADERNO)
        bd.refresh(cuaderno)
        assert cuaderno.nombre_canonico == "cuaderno renombrado"  # lo demas SI se actualiza
        assert cuaderno.admite_personaje is True  # el CSV decia false
        lapiz = bd.get(Concepto, U_LAPIZ)
        bd.refresh(lapiz)
        assert lapiz.admite_personaje is False  # el CSV decia true

    async def test_un_tipo_item_marcado_en_el_csv_sobrevive_a_la_recarga(self, datos, bd):
        """Marcarlo solo en la base no duraba: la carga siguiente lo devolvia a 'util'."""
        filas = leer_csv(datos / "conceptos.csv")
        filas[2]["tipo_item"] = "no_comprar"
        _csv(datos, "conceptos", COLUMNAS_CONCEPTO, filas)
        for _ in range(2):
            c = Cargador(datos)
            await c.escribir(c.armar())
        bd.rollback()
        assert bd.get(Concepto, U_LAPIZ).tipo_item == "no_comprar"


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------


class TestPrincipal:
    async def test_un_problema_bloqueante_devuelve_1_y_no_escribe_nada(self, datos, bd, capsys):
        _csv(datos, "libros_firecrawl", COLUMNAS_LIBRO, [_libro(isbn13=ISBN_MALO)])

        assert await cargador._principal(datos, solo_validar=False) == 1

        salida = capsys.readouterr().out
        assert "No se escribio nada: hay referencias o identificadores rotos." in salida
        assert "[BLOQUEA] isbn" in salida
        assert set(_contar(bd).values()) == {0}

    async def test_solo_validar_informa_con_las_carencias_del_csv_y_no_toca_la_base(self, datos, bd, capsys):
        assert await cargador._principal(datos, solo_validar=True) == 0

        salida = capsys.readouterr().out
        assert "(--solo-validar: las carencias son las de los CSV, no las de la base)" in salida
        assert "productos sin imagen" in salida
        assert set(_contar(bd).values()) == {0}

    async def test_cargar_escribe_y_mide_las_carencias_contra_la_base(self, datos, bd, monkeypatch, capsys):
        async def medir_falso():
            return {"productos sin imagen": (7, 10)}

        monkeypatch.setattr(cargador, "medir_en_bd", medir_falso)

        assert await cargador._principal(datos, solo_validar=False) == 0

        salida = capsys.readouterr().out
        assert "productos sin imagen" in salida
        assert "7/10" in salida
        assert "--solo-validar" not in salida
        assert _contar(bd)["producto_canonico"] == 2


class _Resultado:
    def __init__(self, fila):
        self._fila = fila

    def one(self):
        return self._fila


class _MotorFalso:
    """Un motor cuyas dos consultas devuelven filas fijas (el SQL es de Postgres)."""

    def __init__(self, respuestas):
        self.engine = self
        self.respuestas = list(respuestas)
        self.cerrado = False
        self.sentencias: list[str] = []

    @asynccontextmanager
    async def begin(self):
        yield self

    async def execute(self, sentencia):
        self.sentencias.append(str(sentencia))
        return _Resultado(self.respuestas.pop(0))

    async def cerrar(self):
        self.cerrado = True


async def test_medir_en_bd_mapea_las_dos_consultas_a_las_cinco_carencias(monkeypatch):
    motor = _MotorFalso(
        [
            SimpleNamespace(total=200, sin_imagen=30, sin_atributos=20, empaque_no_leido=5),
            SimpleNamespace(total=60, sin_producto=4, sin_tres_niveles=25),
        ]
    )
    monkeypatch.setattr("tukit_comun.bd.crear_motor", lambda _servicio: motor)

    medidas = await cargador.medir_en_bd()

    assert medidas == {
        "productos sin imagen": (30, 200),
        "productos sin un atributo que filtra": (20, 200),
        "empaque anunciado en el nombre y no leido": (5, 200),
        "conceptos sin ningun producto": (4, 60),
        "conceptos sin los 3 niveles": (25, 60),
    }
    assert motor.cerrado is True
    assert len(motor.sentencias) == 2
    assert "no_comprar" in motor.sentencias[1]  # lo que no se surte no cuenta como hueco


class TestMain:
    def test_un_directorio_que_no_existe_sale_con_2(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["cargador", "--datos", str(tmp_path / "no_existe")])
        assert cargador.main() == 2
        assert "No existe el directorio de datos" in capsys.readouterr().out

    def test_solo_validar_recorre_los_csv_y_sale_con_0(self, datos, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["cargador", "--datos", str(datos), "--solo-validar"])
        assert cargador.main() == 0
        assert "=== cargado ===" in capsys.readouterr().out

    def test_solo_validar_con_un_bloqueo_sale_con_1(self, datos, monkeypatch):
        _csv(datos, "libros_firecrawl", COLUMNAS_LIBRO, [_libro(isbn13=ISBN_MALO)])
        monkeypatch.setattr("sys.argv", ["cargador", "--datos", str(datos), "--solo-validar"])
        assert cargador.main() == 1
