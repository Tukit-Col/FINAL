"""NFR-MAN-01: el volcado base -> CSV decide que es catalogo y que se espeja.

`volcar` es la mitad que cierra el circulo de reproducibilidad: lo que se cura en
la base viva (dashboard, cola de revision) tiene que volver a los CSV
versionados, y SOLO lo curado. Estas pruebas caracterizan las decisiones, no el
pegamento:

- Que fila es catalogo y cual es candidato de maquina o libro sintetizado
  (`_es_curado`): un error aqui mete basura sin revisar al corpus de la tesis, o
  saca del corpus lo que una persona aprobo.
- Como se serializa cada valor para que `cargador` lo lea de vuelta identico
  (nulo -> vacio, tres decimales, fechas ISO, atributos en JSON ordenado).
- Como se fusiona con el CSV existente: el espejo de MEMBRESIA (lo que se borro en
  la base se borra del CSV) y la autoridad por columna (la base manda salvo
  `quality_score`, que `nivelar` deriva sobre el CSV; `nivel` y `atributos`
  son de la base desde 6c29c83).
- Que el volcado es determinista e idempotente (dos corridas, mismo fichero byte
  a byte) y que el modo ensayo no toca el disco.

La base es SQLite en un fichero dentro de `tmp_path`, inyectada en lugar del motor
de Postgres; los CSV viven tambien en `tmp_path`, nunca en `datos/`.
"""

from __future__ import annotations

import csv
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, delete, event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from tukit_catalogo import volcar
from tukit_catalogo.cargador import AGENTE_FIRECRAWL, leer_csv
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


# ---------------------------------------------------------------------------
# Base de prueba: SQLite en fichero, en lugar del motor de Postgres
# ---------------------------------------------------------------------------


def _activar_fk(conexion, _registro):  # noqa: ANN001
    conexion.execute("PRAGMA foreign_keys=ON")


@pytest.fixture()
def bd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Sesion sincrona para sembrar, y `crear_motor` apuntando al mismo fichero.

    En fichero y no en memoria porque el codigo bajo prueba abre un motor nuevo en
    cada llamada y lo dispone al terminar: una base en memoria desapareceria.
    """
    archivo = tmp_path / "catalogo.db"
    sincrono = create_engine(f"sqlite:///{archivo}")
    event.listen(sincrono, "connect", _activar_fk)
    Base.metadata.create_all(sincrono)

    def fabricar(servicio: str, *, echo: bool = False) -> MotorServicio:
        motor = create_async_engine(f"sqlite+aiosqlite:///{archivo}")
        event.listen(motor.sync_engine, "connect", _activar_fk)
        return MotorServicio(servicio, motor, async_sessionmaker(motor, expire_on_commit=False))

    monkeypatch.setattr("tukit_comun.bd.crear_motor", fabricar)
    with Session(sincrono) as sesion:
        yield sesion
    sincrono.dispose()


@pytest.fixture()
def datos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Directorio de CSV de prueba: `volcar.DATOS` nunca apunta a `datos/` real."""
    carpeta = tmp_path / "csv"
    carpeta.mkdir()
    monkeypatch.setattr(volcar, "DATOS", carpeta)
    return carpeta


def _producto(sesion: Session, concepto: Concepto, sku: str, **kw) -> ProductoCanonico:
    p = ProductoCanonico(
        concepto_id=concepto.id,
        sku_interno=sku,
        nombre=kw.pop("nombre", f"Producto {sku}"),
        nivel=kw.pop("nivel", "confiable"),
        curado_por=kw.pop("curado_por", CURADOR),
        **kw,
    )
    sesion.add(p)
    sesion.flush()
    return p


def _oferta(sesion: Session, producto: ProductoCanonico, tienda: Tienda, ref: str, **kw) -> OfertaTienda:
    o = OfertaTienda(
        producto_canonico_id=producto.id,
        tienda_id=tienda.id,
        referencia_externa=ref,
        metodo_vinculacion="manual",
        confianza_vinculacion=1.0,
        **kw,
    )
    sesion.add(o)
    sesion.flush()
    return o


def _precio(sesion: Session, oferta: OfertaTienda, centavos: int) -> PrecioOferta:
    pr = PrecioOferta(
        oferta_id=oferta.id,
        valor_centavos=centavos,
        moneda="COP",
        fuente="scraper",
        vigente_desde=datetime(2026, 9, 1, tzinfo=UTC),
    )
    sesion.add(pr)
    sesion.flush()
    return pr


def _escribir_csv(ruta: Path, columnas: list[str], filas: list[dict[str, str]]) -> None:
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)


# ---------------------------------------------------------------------------
# Que es catalogo curado
# ---------------------------------------------------------------------------


class TestQueFilaEsCatalogoCurado:
    """`_es_curado` es el filtro de entrada al corpus versionado."""

    @pytest.mark.parametrize(
        ("sku", "curado_por", "esperado"),
        [
            ("TK-C001-CON", CURADOR, True),  # curaduria humana de siempre
            ("TK-REV-12345", AGENTE_FIRECRAWL, True),  # aprobado en la cola: SI es catalogo
            ("TK-LIB-9789580000000", CURADOR, False),  # libro sintetizado por el cargador
            ("TK-SUG-77", CURADOR, False),  # sugerencia de maquina sin revisar
            ("TMP-corrida-vieja", CURADOR, False),  # staging
            ("TK-OTRO-1", AGENTE_FIRECRAWL, False),  # sin prefijo conocido, pero lo trajo el raspado
            (None, CURADOR, True),  # sin sku, lo decide el curador
            (None, AGENTE_FIRECRAWL, False),
            ("", str(AGENTE_FIRECRAWL), False),  # el curador puede llegar como texto
        ],
    )
    def test_decide_por_prefijo_y_por_agente(self, sku, curado_por, esperado):
        """Dos senales cruzadas: el prefijo del SKU y el agente que curo la fila.

        El prefijo `TK-REV-` gana sobre el agente (lo aprobo una persona aunque el
        `curado_por` sea el agente); los prefijos no curados ganan sobre un
        curador humano (la fila es sintetizada o sin revisar).
        """
        assert volcar._es_curado(sku, curado_por) is esperado


# ---------------------------------------------------------------------------
# Serializacion base -> texto CSV
# ---------------------------------------------------------------------------


class TestSerializacionAlCsv:
    """Cada helper invierte lo que `cargador` hace al leer."""

    def test_un_nulo_y_una_cadena_vacia_colapsan_a_vacio(self):
        assert volcar._s(None) == ""
        assert volcar._s("") == ""
        assert volcar._s(0) == "0"  # el cero NO es un nulo
        assert volcar._s(uuid.UUID(int=1)) == "00000000-0000-0000-0000-000000000001"

    def test_el_booleano_conserva_el_no_se_como_vacio(self):
        """`disponible` nulo (no se si hay) no puede volverse 'false' (no hay)."""
        assert volcar._bool_csv(True) == "true"
        assert volcar._bool_csv(False) == "false"
        assert volcar._bool_csv(None) == ""

    def test_los_numericos_salen_con_tres_decimales(self):
        assert volcar._num3(Decimal("0.4")) == "0.400"
        assert volcar._num3(1) == "1.000"
        assert volcar._num3(None) == ""

    def test_la_fecha_sale_iso_con_su_zona(self):
        momento = datetime(2026, 9, 2, 12, 30, tzinfo=UTC)
        assert volcar._fecha_csv(momento) == "2026-09-02T12:30:00+00:00"
        assert volcar._fecha_csv(None) == ""

    def test_los_atributos_salen_en_json_ordenado_o_como_llegaron(self):
        assert volcar._atributos_csv(None) == "{}"
        assert volcar._atributos_csv({}) == "{}"
        # Orden por clave y sin escapar tildes: el diff del CSV debe ser estable.
        assert volcar._atributos_csv({"rayado": "cuadriculado", "hojas": 100, "ñ": "á"}) == (
            '{"hojas": 100, "rayado": "cuadriculado", "ñ": "á"}'
        )
        assert volcar._atributos_csv('{"ya": "texto"}') == '{"ya": "texto"}'

    def test_la_fila_de_producto_trae_todas_las_columnas_del_cargador(self):
        """El orden y el conjunto de columnas son los que `cargador` espera leer."""
        p = SimpleNamespace(
            id=uuid.UUID(int=1),
            concepto_id=uuid.UUID(int=2),
            ean=None,
            sku_interno="TK-C001-A",
            nombre="Cuaderno Ficticio",
            descripcion=None,
            marca="Marca Ficticia",
            nivel="confiable",
            personaje=None,
            imagen_url=None,
            atributos={"hojas": 100},
            # El empaque se vuelca desde 67ee3f2 (volcar.py:247-248): el CSV manda en el.
            unidad_base="unidad",
            unidades_por_empaque=12,
            ruta_categoria=None,
            es_propio=False,
            grupo_variante_id=None,
            es_representante_canonico=None,
            embedding=[0.1, 0.2],
            embedding_model="modelo-falso",
            texto_embedding="cuaderno",
            quality_score=Decimal("0.7"),
            activo=True,
            curado_por=CURADOR,
            curado_en=datetime(2026, 9, 1, tzinfo=UTC),
        )
        fila = volcar._fila_producto(p)
        assert list(fila) == volcar.COLUMNAS_PRODUCTO
        assert fila["embedding"] == ""  # el vector no se versiona, aunque la base lo tenga
        assert fila["embedding_model"] == "modelo-falso"  # la huella si
        assert fila["quality_score"] == "0.700"
        assert fila["es_propio"] == "false"
        assert fila["es_representante_canonico"] == ""
        assert fila["atributos"] == '{"hojas": 100}'
        assert (fila["unidad_base"], fila["unidades_por_empaque"]) == ("unidad", "12")
        assert fila["curado_por"] == str(CURADOR)

    def test_la_procedencia_sale_de_la_oferta_representante(self):
        p = SimpleNamespace(id=uuid.UUID(int=1), sku_interno="TK-REV-9")
        oferta_id = uuid.UUID(int=10)
        tienda_id = uuid.UUID(int=20)
        oferta = SimpleNamespace(
            id=oferta_id, tienda_id=tienda_id, referencia_externa="R-9", url="https://x.test/p"
        )
        fila = volcar._fila_procedencia(p, oferta, {str(tienda_id): "exito"}, {str(oferta_id): 1865049})
        assert fila == {
            "producto_id": str(p.id),
            "sku_interno": "TK-REV-9",
            "fichero_fuente": "cola_revision",
            "sha256_fichero": "",
            "indice_en_fichero": "R-9",
            "tienda_origen": "exito",
            "referencia_origen": "R-9",
            "url_origen": "https://x.test/p",
            # centavos -> pesos con redondeo, no truncado
            "precio_observado_cop": "18650",
        }
        assert list(fila) == volcar.COLUMNAS_PROCEDENCIA

    def test_la_procedencia_sin_oferta_deja_los_datos_de_origen_vacios(self):
        """Un producto sin oferta igual tiene fila de procedencia (el corpus la exige)."""
        p = SimpleNamespace(id=uuid.UUID(int=1), sku_interno="TK-C001-B")
        fila = volcar._fila_procedencia(p, None, {}, {})
        assert fila["fichero_fuente"] == "cola_revision"
        assert fila["tienda_origen"] == fila["referencia_origen"] == fila["url_origen"] == ""
        assert fila["precio_observado_cop"] == ""

    def test_la_procedencia_con_oferta_sin_precio_no_inventa_uno(self):
        p = SimpleNamespace(id=uuid.UUID(int=1), sku_interno="TK-C001-C")
        oferta = SimpleNamespace(
            id=uuid.UUID(int=10), tienda_id=uuid.UUID(int=20), referencia_externa="R", url=None
        )
        fila = volcar._fila_procedencia(p, oferta, {}, {})
        assert fila["precio_observado_cop"] == ""
        assert fila["tienda_origen"] == ""  # tienda desconocida: vacio, no revienta
        assert fila["url_origen"] == ""


# ---------------------------------------------------------------------------
# Fusion con el CSV existente
# ---------------------------------------------------------------------------


class TestFusionDeOfertasYPrecios:
    """Espejo de membresia: la base decide QUE filas existen."""

    def test_quita_lo_borrado_conserva_lo_vivo_y_agrega_lo_nuevo(self):
        existentes = [
            {"id": "a", "url": "vieja-a"},
            {"id": "b", "url": "vieja-b"},
            {"id": "borrada", "url": "x"},
        ]
        nuevas = {"a": {"id": "a", "url": "NUEVA-a"}, "c": {"id": "c", "url": "nueva-c"}}
        filas, agregadas, eliminadas = volcar._fusionar(existentes, nuevas, ids_vivos={"a", "b", "c"})
        # `a` conserva lo que el CSV ya tenia (no se re-serializa); `b` sigue viva
        # aunque ya no venga en `nuevas`; `c` entra desde la base.
        assert filas == [
            {"id": "a", "url": "vieja-a"},
            {"id": "b", "url": "vieja-b"},
            {"id": "c", "url": "nueva-c"},
        ]
        assert (agregadas, eliminadas) == (1, 1)

    def test_sin_cambios_es_el_mismo_csv(self):
        existentes = [{"id": "a"}, {"id": "b"}]
        filas, agregadas, eliminadas = volcar._fusionar(existentes, {"a": {"id": "a"}}, {"a", "b"})
        assert filas == existentes
        assert (agregadas, eliminadas) == (0, 0)


class TestFusionDeProductos:
    """La base manda, salvo en las columnas que cura el CSV."""

    def test_la_base_pisa_lo_editado_nivel_y_atributos_incluidos_y_el_csv_conserva_la_calidad(self):
        """Desde 6c29c83 `nivel` y `atributos` son de la base (volcar.py:322-343).

        El nivel que se cambia en el editor y los atributos corregidos a mano
        viven en la base, y el cargador ya lee los atributos del CSV; conservar
        los del CSV los perdia al exportar. Solo `quality_score` sigue del CSV.
        """
        existentes = [
            {
                "id": "p1",
                "nombre": "Nombre viejo",
                "concepto_id": "concepto-viejo",
                "nivel": "premium",  # lo reacomodo `nivelar` sobre el CSV
                "quality_score": "0.950",
                "atributos": '{"curado": "a mano"}',
            }
        ]
        desde_bd = {
            "p1": {
                "id": "p1",
                "nombre": "Nombre editado en el dashboard",
                "concepto_id": "concepto-nuevo",
                "nivel": "economico",
                "quality_score": "0.400",
                "atributos": "{}",
            }
        }
        filas, nuevas, eliminadas = volcar._fusionar_productos(existentes, desde_bd)
        assert filas == [
            {
                "id": "p1",
                "nombre": "Nombre editado en el dashboard",  # la base manda
                "concepto_id": "concepto-nuevo",  # reasignar concepto llega al corpus
                "nivel": "economico",  # la base manda: lo edito el back-office
                "quality_score": "0.950",  # el CSV manda
                "atributos": "{}",  # la base manda
            }
        ]
        assert (nuevas, eliminadas) == (0, 0)

    def test_un_producto_nuevo_entra_tal_cual_lo_serializo_la_base(self):
        desde_bd = {"p2": {"id": "p2", "nivel": "economico", "quality_score": "0.400", "atributos": "{}"}}
        filas, nuevas, eliminadas = volcar._fusionar_productos([], desde_bd)
        assert filas == [desde_bd["p2"]]
        assert (nuevas, eliminadas) == (1, 0)

    def test_lo_borrado_de_la_base_se_borra_del_csv(self):
        """Un hard delete en el dashboard no puede resucitar con la proxima carga."""
        existentes = [{"id": "maleta", "nivel": "confiable"}, {"id": "p1", "nivel": "confiable"}]
        filas, nuevas, eliminadas = volcar._fusionar_productos(existentes, {"p1": {"id": "p1", "nivel": "x"}})
        assert [f["id"] for f in filas] == ["p1"]
        assert (nuevas, eliminadas) == (0, 1)

    def test_el_conteo_mezcla_nuevas_y_borradas_sin_confundirlas(self):
        existentes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        desde_bd = {"a": {"id": "a"}, "d": {"id": "d"}, "e": {"id": "e"}}
        filas, nuevas, eliminadas = volcar._fusionar_productos(existentes, desde_bd)
        assert sorted(f["id"] for f in filas) == ["a", "d", "e"]
        assert (nuevas, eliminadas) == (2, 2)

    def test_una_columna_propia_ausente_en_el_csv_viejo_no_rompe(self):
        """Un CSV viejo sin `quality_score` no puede borrar la columna al fusionar.

        Desde 6c29c83 la unica columna propia del CSV es `quality_score`.
        """
        existentes = [{"id": "p1", "nivel": "premium"}]
        desde_bd = {"p1": {"id": "p1", "nivel": "economico", "atributos": "{}", "quality_score": "0.4"}}
        filas, _, _ = volcar._fusionar_productos(existentes, desde_bd)
        assert filas[0]["nivel"] == "economico"
        assert filas[0]["atributos"] == "{}"
        assert filas[0]["quality_score"] == "0.4"

    def test_la_unica_columna_del_csv_es_la_calidad(self):
        """Ampliar este conjunto cambia quien manda sobre el corpus: se fija a proposito.

        Eran tres hasta 6c29c83, que le devolvio `nivel` y `atributos` a la base
        (volcar.py:343).
        """
        assert set(volcar.COLUMNAS_PROPIAS_DEL_CSV) == {"quality_score"}


class TestFusionDeProcedencia:
    def test_se_identifica_por_producto_no_por_id_propio(self):
        """La huella de origen se conserva; el SKU, desde 6c29c83, es el vigente de la base.

        Un SKU re-acunado al reclasificar llega a la fila conservada (volcar.py:414-420).
        """
        existentes = [
            {"producto_id": "p1", "sku_interno": "TK-C001-A", "fichero_fuente": "feed.json"},  # semilla
            {"producto_id": "borrado", "sku_interno": "TK-C001-X", "fichero_fuente": "feed.json"},
        ]
        nuevas = {
            "p1": {"producto_id": "p1", "sku_interno": "TK-C002-A", "fichero_fuente": "cola_revision"},
            "p2": {"producto_id": "p2", "sku_interno": "TK-C001-B", "fichero_fuente": "cola_revision"},
        }
        filas, agregadas, eliminadas = volcar._fusionar_procedencia(existentes, nuevas, {"p1", "p2"})
        assert filas == [
            # la semilla no se pisa, salvo el SKU vigente
            {"producto_id": "p1", "sku_interno": "TK-C002-A", "fichero_fuente": "feed.json"},
            {"producto_id": "p2", "sku_interno": "TK-C001-B", "fichero_fuente": "cola_revision"},
        ]
        assert (agregadas, eliminadas) == (1, 1)


# ---------------------------------------------------------------------------
# Escritura de ficheros
# ---------------------------------------------------------------------------


class TestGuardar:
    def test_escribe_cabecera_y_filas_ordenadas_por_la_clave(self, datos):
        columnas = ["id", "sku_interno"]
        filas = [
            {"id": "2", "sku_interno": "TK-B"},
            {"id": "1", "sku_interno": "TK-C"},
            {"id": "3", "sku_interno": "TK-A"},
        ]
        volcar._guardar("demo", columnas, filas, "sku_interno")
        texto = (datos / "demo.csv").read_text(encoding="utf-8")
        assert texto.splitlines() == ["id,sku_interno", "3,TK-A", "2,TK-B", "1,TK-C"]

    def test_un_valor_con_comas_y_comillas_vuelve_igual_al_leerlo(self, datos):
        fila = {"id": "1", "nombre": 'Regla 30 cm, "flexible"\ny verde'}
        volcar._guardar("demo", ["id", "nombre"], [fila], "id")
        assert leer_csv(datos / "demo.csv") == [fila]

    def test_el_mismo_contenido_da_el_mismo_fichero_byte_a_byte(self, datos):
        filas = [{"id": "b", "x": "1"}, {"id": "a", "x": "2"}]
        volcar._guardar("demo", ["id", "x"], filas, "id")
        primero = (datos / "demo.csv").read_bytes()
        volcar._guardar("demo", ["id", "x"], list(reversed(filas)), "id")
        assert (datos / "demo.csv").read_bytes() == primero


# ---------------------------------------------------------------------------
# El volcado completo contra una base real (SQLite)
# ---------------------------------------------------------------------------


def _sembrar(bd: Session) -> dict[str, uuid.UUID]:
    """Una base con una de cada clase de fila: curada, libro, sugerencia, aprobada, raspada."""
    exito = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    pana = Tienda(slug="panamericana", nombre="Panamericana", tipo="minorista")
    concepto = Concepto(codigo="C001", nombre_canonico="cuaderno", categoria="papeleria")
    bd.add_all([exito, pana, concepto])
    bd.flush()

    curado = _producto(bd, concepto, "TK-C001-A", nombre="Cuaderno Ficticio Curado")
    sin_oferta = _producto(bd, concepto, "TK-C001-B", nombre="Cuaderno Ficticio Sin Oferta")
    aprobado = _producto(
        bd, concepto, "TK-REV-777", nombre="Cuaderno Ficticio Aprobado", curado_por=AGENTE_FIRECRAWL
    )
    libro = _producto(
        bd, concepto, "TK-LIB-9789580000000", nombre="Libro Ficticio", curado_por=AGENTE_FIRECRAWL
    )
    sugerido = _producto(bd, concepto, "TK-SUG-1", nombre="Sugerido Ficticio")
    raspado = _producto(bd, concepto, "TK-RARO-1", nombre="Raspado Ficticio", curado_por=AGENTE_FIRECRAWL)

    # El curado tiene dos ofertas: la que no tiene precio no puede ser la
    # representante aunque venga primero; gana la que si tiene precio.
    o_sin_precio = _oferta(bd, curado, exito, "R-SIN-PRECIO", url="https://exito.test/sin-precio")
    o_con_precio = _oferta(bd, curado, pana, "R-CON-PRECIO", url="https://pana.test/con-precio")
    _precio(bd, o_con_precio, 900000)
    # El aprobado tiene dos ofertas con precio: gana la mas barata.
    o_cara = _oferta(bd, aprobado, exito, "R-CARA", url="https://exito.test/cara")
    o_barata = _oferta(bd, aprobado, pana, "R-BARATA", url="https://pana.test/barata")
    _precio(bd, o_cara, 2500000)
    _precio(bd, o_barata, 1865049)
    # Ofertas y precios de las filas que NO son catalogo: tienen que quedar fuera.
    o_libro = _oferta(bd, libro, exito, "R-LIBRO")
    _precio(bd, o_libro, 5000000)
    o_sug = _oferta(bd, sugerido, exito, "R-SUG")
    _precio(bd, o_sug, 100000)
    o_raspado = _oferta(bd, raspado, pana, "R-RASPADO")
    _precio(bd, o_raspado, 300000)
    bd.commit()
    return {
        "curado": curado.id,
        "sin_oferta": sin_oferta.id,
        "aprobado": aprobado.id,
        "libro": libro.id,
        "sugerido": sugerido.id,
        "raspado": raspado.id,
        "o_sin_precio": o_sin_precio.id,
        "o_con_precio": o_con_precio.id,
        "o_cara": o_cara.id,
        "o_barata": o_barata.id,
        "o_libro": o_libro.id,
        "o_sug": o_sug.id,
        "o_raspado": o_raspado.id,
    }


async def test_leer_base_trae_las_cuatro_tablas(bd):
    ids = _sembrar(bd)
    base = await volcar._leer_base()
    assert set(base) == {"productos", "ofertas", "precios", "tiendas"}
    assert len(base["productos"]) == 6
    assert len(base["ofertas"]) == 7
    assert len(base["precios"]) == 6
    assert {t.slug for t in base["tiendas"]} == {"exito", "panamericana"}
    assert ids["curado"] in {p.id for p in base["productos"]}


async def test_el_ensayo_informa_y_no_toca_ningun_fichero(bd, datos, capsys):
    """Sin `--escribir` el volcado solo cuenta: el diff de `datos/` debe seguir vacio."""
    _sembrar(bd)
    anterior = "id,concepto_id\nviejo,viejo\n"
    (datos / "productos_canonicos.csv").write_text(anterior, encoding="utf-8")

    codigo = await volcar._principal(solo_ensayo=True)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "Ensayo. Sin --escribir no se toca ningun fichero." in salida
    assert (datos / "productos_canonicos.csv").read_text(encoding="utf-8") == anterior
    assert sorted(p.name for p in datos.iterdir()) == ["productos_canonicos.csv"]


async def test_solo_lo_curado_llega_al_csv_con_sus_ofertas_y_precios(bd, datos, capsys):
    """Libros, sugerencias y lo raspado sin revisar se descartan junto con sus hijos."""
    ids = _sembrar(bd)

    assert await volcar._principal(solo_ensayo=False) == 0

    productos = leer_csv(datos / "productos_canonicos.csv")
    assert [p["sku_interno"] for p in productos] == ["TK-C001-A", "TK-C001-B", "TK-REV-777"]  # orden por sku
    ofertas = leer_csv(datos / "ofertas_tienda.csv")
    assert {o["id"] for o in ofertas} == {
        str(ids["o_sin_precio"]),
        str(ids["o_con_precio"]),
        str(ids["o_cara"]),
        str(ids["o_barata"]),
    }
    precios = leer_csv(datos / "precios_oferta.csv")
    assert {pr["oferta_id"] for pr in precios} == {
        str(ids["o_con_precio"]),
        str(ids["o_cara"]),
        str(ids["o_barata"]),
    }
    assert all(pr["moneda"] == "COP" for pr in precios)
    salida = capsys.readouterr().out
    assert "3 no curados omitidos" in salida
    assert "Escrito." in salida


async def test_la_procedencia_elige_la_oferta_mas_barata_y_tolera_la_que_no_tiene_precio(bd, datos):
    """Cada producto vuelcado lleva su origen; el representante es el de menor precio."""
    _sembrar(bd)

    await volcar._principal(solo_ensayo=False)

    procedencia = {p["sku_interno"]: p for p in leer_csv(datos / "productos_procedencia.csv")}
    assert set(procedencia) == {"TK-C001-A", "TK-C001-B", "TK-REV-777"}
    # El aprobado tiene dos precios: 25.000 (exito) y 18.650,49 (pana) -> pana, redondeado.
    assert procedencia["TK-REV-777"]["tienda_origen"] == "panamericana"
    assert procedencia["TK-REV-777"]["referencia_origen"] == "R-BARATA"
    assert procedencia["TK-REV-777"]["precio_observado_cop"] == "18650"
    # El curado: la oferta sin precio pierde contra la que si lo tiene.
    assert procedencia["TK-C001-A"]["tienda_origen"] == "panamericana"
    assert procedencia["TK-C001-A"]["precio_observado_cop"] == "9000"
    # El que no tiene oferta igual tiene fila (el corpus exige una por producto).
    assert procedencia["TK-C001-B"]["tienda_origen"] == ""
    assert procedencia["TK-C001-B"]["precio_observado_cop"] == ""
    assert all(
        p["fichero_fuente"] == "cola_revision" and p["sha256_fichero"] == "" for p in procedencia.values()
    )


async def test_el_espejo_conserva_lo_curado_en_el_csv_y_quita_lo_borrado(bd, datos, capsys):
    """Fusion contra un CSV previo: calidad del CSV; nombre, nivel y atributos de la base; fantasma eliminado.

    `nivel` y `atributos` son de la base desde 6c29c83 (volcar.py:322-343).
    """
    ids = _sembrar(bd)
    _escribir_csv(
        datos / "productos_canonicos.csv",
        volcar.COLUMNAS_PRODUCTO,
        [
            {
                **dict.fromkeys(volcar.COLUMNAS_PRODUCTO, ""),
                "id": str(ids["curado"]),
                "sku_interno": "TK-C001-A",
                "nombre": "Nombre viejo del CSV",
                "nivel": "premium",
                "quality_score": "0.950",
                "atributos": '{"curado": "a mano"}',
            },
            {
                **dict.fromkeys(volcar.COLUMNAS_PRODUCTO, ""),
                "id": str(uuid.uuid4()),
                "sku_interno": "TK-FANTASMA",
                "nombre": "Borrado en el dashboard",
            },
        ],
    )

    await volcar._principal(solo_ensayo=False)

    productos = {p["sku_interno"]: p for p in leer_csv(datos / "productos_canonicos.csv")}
    assert "TK-FANTASMA" not in productos
    curado = productos["TK-C001-A"]
    assert curado["nombre"] == "Cuaderno Ficticio Curado"  # la base manda sobre el nombre
    assert curado["nivel"] == "confiable"  # y sobre el nivel
    assert curado["quality_score"] == "0.950"
    assert curado["atributos"] == "{}"  # y sobre los atributos
    salida = capsys.readouterr().out
    assert "+2 nuevos, -1 borrados" in salida


async def test_dos_volcados_seguidos_dan_los_mismos_ficheros_byte_a_byte(bd, datos):
    """Idempotencia: sin cambios en la base, volcar de nuevo no produce diff."""
    _sembrar(bd)
    nombres = ("productos_canonicos", "ofertas_tienda", "precios_oferta", "productos_procedencia")

    await volcar._principal(solo_ensayo=False)
    primero = {n: (datos / f"{n}.csv").read_bytes() for n in nombres}
    await volcar._principal(solo_ensayo=False)

    assert {n: (datos / f"{n}.csv").read_bytes() for n in nombres} == primero


async def test_borrar_un_producto_en_la_base_lo_quita_del_csv_en_el_siguiente_volcado(bd, datos):
    """El hard delete del dashboard llega al corpus: ni producto, ni oferta, ni procedencia."""
    ids = _sembrar(bd)
    await volcar._principal(solo_ensayo=False)

    bd.execute(delete(PrecioOferta).where(PrecioOferta.oferta_id.in_([ids["o_cara"], ids["o_barata"]])))
    bd.execute(delete(OfertaTienda).where(OfertaTienda.producto_canonico_id == ids["aprobado"]))
    bd.execute(delete(ProductoCanonico).where(ProductoCanonico.id == ids["aprobado"]))
    bd.commit()

    await volcar._principal(solo_ensayo=False)

    assert [p["sku_interno"] for p in leer_csv(datos / "productos_canonicos.csv")] == [
        "TK-C001-A",
        "TK-C001-B",
    ]
    assert {o["id"] for o in leer_csv(datos / "ofertas_tienda.csv")} == {
        str(ids["o_sin_precio"]),
        str(ids["o_con_precio"]),
    }
    assert {p["sku_interno"] for p in leer_csv(datos / "productos_procedencia.csv")} == {
        "TK-C001-A",
        "TK-C001-B",
    }
    assert {pr["oferta_id"] for pr in leer_csv(datos / "precios_oferta.csv")} == {str(ids["o_con_precio"])}


async def test_una_base_vacia_deja_los_csv_solo_con_cabecera(bd, datos):
    await volcar._principal(solo_ensayo=False)
    for nombre, columnas in (
        ("productos_canonicos", volcar.COLUMNAS_PRODUCTO),
        ("ofertas_tienda", volcar.COLUMNAS_OFERTA),
        ("precios_oferta", volcar.COLUMNAS_PRECIO),
        ("productos_procedencia", volcar.COLUMNAS_PROCEDENCIA),
    ):
        assert (datos / f"{nombre}.csv").read_text(encoding="utf-8").strip() == ",".join(columnas)


class TestMain:
    """La bandera `--escribir` es la unica diferencia entre informar y escribir."""

    def test_sin_bandera_corre_en_modo_ensayo(self, monkeypatch):
        visto = {}

        async def falso(solo_ensayo: bool) -> int:
            visto["solo_ensayo"] = solo_ensayo
            return 0

        monkeypatch.setattr(volcar, "_principal", falso)
        monkeypatch.setattr("sys.argv", ["volcar"])
        assert volcar.main() == 0
        assert visto == {"solo_ensayo": True}

    def test_con_escribir_deja_de_ser_ensayo(self, monkeypatch):
        visto = {}

        async def falso(solo_ensayo: bool) -> int:
            visto["solo_ensayo"] = solo_ensayo
            return 0

        monkeypatch.setattr(volcar, "_principal", falso)
        monkeypatch.setattr("sys.argv", ["volcar", "--escribir"])
        assert volcar.main() == 0
        assert visto == {"solo_ensayo": False}
