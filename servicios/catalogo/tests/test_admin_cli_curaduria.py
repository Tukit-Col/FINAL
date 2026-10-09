"""NFR-MAN-01: la consola de curaduria edita el catalogo sin romper lo que el catalogo promete.

`test_admin` lee el codigo fuente de esta consola y pinta HTML con diccionarios
armados a mano; aqui se EJERCE de verdad contra un esquema SQLite real, sin
tiendas (`tiendas.buscar` se sustituye) y sin abrir un puerto (el manejador HTTP
se invoca con buffers en memoria). Se fija:

- **Que se edita y que no.** Editar un producto cambia solo lo que llega: una
  cadena vacia borra a proposito, `None` no toca; un producto o concepto
  inexistente o inactivo se rechaza sin escribir nada.
- **Que se borra.** Quitar un producto se lleva sus precios, ofertas y la
  propuesta aprobada que lo apuntaba, y solo a el.
- **Que se descarta.** `no_surtir` marca el concepto y rechaza SUS pendientes,
  no las de otro concepto ni las ya aprobadas.
- **Que se agrega.** Un util o un libro elegidos nacen como producto con su
  oferta y precio por el mismo camino que una lista revisada; un ISBN con digito
  de control malo no entra; repetirlo no duplica.
- **Que se confia del navegador.** El alta de un util vuelve a buscar y toma el
  candidato por SKU: el precio y la ficha salen de la tienda, no del cliente.
- **Que el servidor no se cae.** Un error de curaduria devuelve JSON y el servidor
  sigue; escucha solo en el loopback.

Detalle de SQLite: los UUID se guardan como 32 hex sin guiones, asi que las
pruebas pasan los ids como `.hex` (Postgres acepta el UUID con guiones que
manda el navegador; la sentencia es la misma). `_leer` usa `LEFT JOIN LATERAL`,
que SQLite no tiene: se prueba con un motor falso que devuelve las filas que el
SQL sacaria.
"""

from __future__ import annotations

import io
import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from tukit_catalogo import admin
from tukit_catalogo.cargador import AGENTE_FIRECRAWL
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
    PropuestaProducto,
    Tienda,
)
from tukit_catalogo.tiendas import Oferta
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

CURADOR = uuid.UUID("00000000-0000-0000-0000-0000000000c1")
ISBN_VALIDO = "9789580714729"


def _activar_fk(conexion, _registro):  # noqa: ANN001
    conexion.execute("PRAGMA foreign_keys=ON")


@pytest.fixture()
def bd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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


def _producto(concepto: Concepto, sku: str, nombre: str, nivel: str = "economico", **kw) -> ProductoCanonico:
    return ProductoCanonico(
        concepto_id=concepto.id, sku_interno=sku, nombre=nombre, nivel=nivel, curado_por=CURADOR, **kw
    )


def _oferta_bd(producto: ProductoCanonico, tienda: Tienda, ref: str, *, activo: bool = True) -> OfertaTienda:
    return OfertaTienda(
        producto_canonico_id=producto.id,
        tienda_id=tienda.id,
        referencia_externa=ref,
        url=f"https://{tienda.slug}.example.test/{ref}",
        metodo_vinculacion="manual",
        confianza_vinculacion=1.0,
        activo=activo,
    )


def _precio_bd(
    oferta: OfertaTienda, centavos: int, desde: datetime, hasta: datetime | None = None
) -> PrecioOferta:
    return PrecioOferta(
        oferta_id=oferta.id,
        valor_centavos=centavos,
        moneda="COP",
        fuente="scraper",
        vigente_desde=desde,
        vigente_hasta=hasta,
    )


def _propuesta(bd: Session, mundo: SimpleNamespace, ref: str, **kw) -> PropuestaProducto:
    datos: dict[str, Any] = {
        "concepto_id": mundo.tijeras.id,
        "texto_origen": "tijeras",
        "tienda_id": mundo.exito.id,
        "referencia_externa": ref,
        "url": f"https://exito.example.test/{ref}",
        "nombre": f"Tijeras Escolares Ficticias {ref}",
        "marca": "Marca Ficticia",
        "ean": None,
        "imagen_url": "https://img.example.test/t.jpg",
        "precio_centavos": 900000,
        "disponible": True,
        "especificaciones": {},
        "nivel_sugerido": "confiable",
        "puntaje": 0.6,
    }
    datos.update(kw)
    p = PropuestaProducto(**datos)
    bd.add(p)
    bd.commit()
    return p


def _sembrar(bd: Session) -> SimpleNamespace:
    """Dos tiendas, tres conceptos y un puñado de productos con precio.

    - cuaderno (C001, demanda 5): economico con una oferta de dos tramos de precio (uno cerrado
      y uno vigente) y confiable; mas un tercero retirado (inactivo).
    - tijeras (C002, demanda 50): un economico con oferta activa en exito y otra inactiva en panamericana.
    - uniforme (C003, demanda 1): sin productos.
    """
    exito = Tienda(slug="exito", nombre="Exito", tipo="minorista")
    panam = Tienda(slug="panamericana", nombre="Panamericana", tipo="minorista")
    cuaderno = Concepto(
        codigo="C001",
        nombre_canonico="cuaderno",
        categoria="escritura",
        sinonimos=["cuaderno cosido"],
        atributos_discriminantes=["hojas"],
        atributos_descriptivos=["material"],
        frecuencia_demanda=5,
    )
    tijeras = Concepto(
        codigo="C002",
        nombre_canonico="tijeras",
        categoria="manualidades",
        sinonimos=[],
        frecuencia_demanda=50,
    )
    uniforme = Concepto(
        codigo="C003", nombre_canonico="uniforme", categoria="vestuario", sinonimos=[], frecuencia_demanda=1
    )
    bd.add_all([exito, panam, cuaderno, tijeras, uniforme])
    bd.flush()
    cuaderno_eco = _producto(cuaderno, "SKU-C1", "Cuaderno Ficticio Uno")
    cuaderno_conf = _producto(cuaderno, "SKU-C2", "Cuaderno Ficticio Dos", "confiable")
    cuaderno_retirado = _producto(cuaderno, "SKU-C3", "Cuaderno Retirado", "premium", activo=False)
    tijera = _producto(tijeras, "SKU-T1", "Tijeras Ficticias")
    bd.add_all([cuaderno_eco, cuaderno_conf, cuaderno_retirado, tijera])
    bd.flush()
    of_cuaderno = _oferta_bd(cuaderno_eco, exito, "C1")
    of_conf = _oferta_bd(cuaderno_conf, exito, "C2")
    of_tijera = _oferta_bd(tijera, exito, "T1")
    of_tijera_inactiva = _oferta_bd(tijera, panam, "T1P", activo=False)
    bd.add_all([of_cuaderno, of_conf, of_tijera, of_tijera_inactiva])
    bd.flush()
    enero, junio = datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 6, 1, tzinfo=UTC)
    bd.add_all(
        [
            _precio_bd(of_cuaderno, 400000, enero, junio),  # tramo cerrado: historia
            _precio_bd(of_cuaderno, 500000, junio),  # el vigente
            _precio_bd(of_conf, 650000, junio),
            _precio_bd(of_tijera, 800000, junio),
            _precio_bd(of_tijera_inactiva, 700000, junio),
        ]
    )
    bd.commit()
    return SimpleNamespace(
        exito=exito,
        panam=panam,
        cuaderno=cuaderno,
        tijeras=tijeras,
        uniforme=uniforme,
        cuaderno_eco=cuaderno_eco,
        cuaderno_conf=cuaderno_conf,
        cuaderno_retirado=cuaderno_retirado,
        tijera=tijera,
        of_cuaderno=of_cuaderno,
        of_tijera=of_tijera,
        of_tijera_inactiva=of_tijera_inactiva,
    )


def _contar(bd: Session, modelo) -> int:  # noqa: ANN001
    bd.rollback()
    return bd.scalar(select(func.count()).select_from(modelo))


def _valores(bd: Session, oferta: OfertaTienda) -> list[tuple[int, bool]]:
    """(valor_centavos, vigente) de los tramos de una oferta, del mas viejo al mas nuevo."""
    bd.rollback()
    filas = bd.execute(
        select(PrecioOferta.valor_centavos, PrecioOferta.vigente_hasta)
        .where(PrecioOferta.oferta_id == oferta.id)
        .order_by(PrecioOferta.vigente_desde)
    ).all()
    return [(valor, hasta is None) for valor, hasta in filas]


def _refrescar(bd: Session, objeto):  # noqa: ANN001, ANN202
    bd.rollback()
    bd.expire_all()
    return objeto


def _oferta_tienda(sku: str = "T9", precio: int = 12000, **kw) -> Oferta:
    datos = {
        "tienda": "exito",
        "nombre": "Tijeras Escolares Candidatas",
        "precio_cop": precio,
        "disponible": True,
        "imagen_url": "https://img.example.test/c.jpg",
        "url": f"https://exito.example.test/{sku}/p",
        "sku": sku,
        "ean": None,
        "marca": "Marca Ficticia",
        "especificaciones": {},
    }
    datos.update(kw)
    return Oferta(**datos)


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


class _Resultado:
    def __init__(self, dato: Any) -> None:
        self.dato = dato

    def all(self) -> list[Any]:
        return self.dato

    def scalar_one(self) -> Any:
        return self.dato


class _MotorFalso:
    """Motor cuyas consultas devuelven filas fijas (el SQL de `_leer` es de Postgres)."""

    def __init__(self, respuestas: list[Any]) -> None:
        self.engine = self
        self.respuestas = list(respuestas)
        self.cerrado = False

    @asynccontextmanager
    async def begin(self):
        yield self

    async def execute(self, _sentencia):  # noqa: ANN001
        return _Resultado(self.respuestas.pop(0))

    async def cerrar(self) -> None:
        self.cerrado = True


def _fila_leer(codigo: str, tipo_item: str = "util", pid: str | None = None, **kw) -> SimpleNamespace:
    datos = {
        "cid": f"cid-{codigo}",
        "codigo": codigo,
        "nombre_canonico": f"concepto {codigo}",
        "tipo_item": tipo_item,
        "frecuencia_demanda": 3,
        "sinonimos": ["sinonimo uno"],
        "atributos_discriminantes": ["hojas"],
        "atributos_descriptivos": ["material"],
        "pid": pid,
        "nombre": f"Producto {pid}" if pid else None,
        "nivel": "economico",
        "imagen_url": "https://img.example.test/p.jpg",
        "personaje": None,
        "marca": None,
        "atributos": {},
        "unidad_base": "unidad",
        "unidades_por_empaque": 1,
        "quality_score": 0.85,
        "tienda": "Exito",
        "url": None,
        "precio": 500000,
    }
    datos.update(kw)
    return SimpleNamespace(**datos)


class TestLeer:
    async def test_agrupa_por_concepto_y_resume_lo_que_hace_falta_curar(self, monkeypatch):
        filas = [
            # A: los tres niveles
            _fila_leer("A", pid="a1", nivel="economico"),
            _fila_leer("A", pid="a2", nivel="confiable", imagen_url=None),
            _fila_leer("A", pid="a3", nivel="premium"),
            # B: comprable y sin un solo producto
            _fila_leer("B"),
            # C: no se surte; su unico producto no tiene puntaje (cuenta como sin revisar)
            _fila_leer("C", tipo_item="no_comprar", pid="c1", quality_score=None),
            # D: dos de tres niveles, uno de ellos con puntaje bajo
            _fila_leer("D", pid="d1", nivel="economico", quality_score=0.3),
            _fila_leer("D", pid="d2", nivel="confiable"),
        ]
        motor = _MotorFalso([filas, 3, 7])
        monkeypatch.setattr("tukit_comun.bd.crear_motor", lambda _s: motor)

        conceptos, resumen = await admin._leer()

        assert [c["codigo"] for c in conceptos] == ["A", "B", "C", "D"]
        assert [len(c["productos"]) for c in conceptos] == [3, 0, 1, 2]
        a = conceptos[0]
        assert a["id"] == "cid-A"
        assert a["atributos_clave"] == ["hojas", "material"]  # los que filtran, primero
        assert a["sinonimos"] == ["sinonimo uno"]
        assert [p["id"] for p in a["productos"]] == ["a1", "a2", "a3"]
        assert resumen == {
            "productos": 6,
            "conceptos": 4,
            "comprables": 3,  # A, B y D: el no_comprar no cuenta
            "completos": 1,  # solo A tiene los tres niveles
            "sin_producto": 1,  # B
            "con_foto": 5,
            "tiendas": 3,
            "por_revisar": 2,  # c1 sin puntaje y d1 con 0.3
            "por_revisar_cola": 7,
        }
        assert motor.cerrado is True

    async def test_sin_nada_en_la_base_el_resumen_es_cero(self, monkeypatch):
        monkeypatch.setattr("tukit_comun.bd.crear_motor", lambda _s: _MotorFalso([[], 0, 0]))
        conceptos, resumen = await admin._leer()
        assert conceptos == []
        assert set(resumen.values()) == {0}


class TestLeerCola:
    async def test_agrupa_por_concepto_ordena_por_demanda_y_pone_lo_nuevo_al_final(self, bd):
        mundo = _sembrar(bd)
        barata = _propuesta(bd, mundo, "Q-BARATA", nivel_sugerido="economico", precio_centavos=300000)
        cara = _propuesta(bd, mundo, "Q-CARA", nivel_sugerido="premium", precio_centavos=2000000)
        media = _propuesta(bd, mundo, "Q-MEDIA", nivel_sugerido="confiable", precio_centavos=900000)
        _propuesta(bd, mundo, "Q-UNI", concepto_id=mundo.uniforme.id, nivel_sugerido=None)
        nuevo = _propuesta(
            bd, mundo, "Q-NUEVO", concepto_id=None, concepto_sugerido="aserrin colores", puntaje=0.3
        )
        _propuesta(bd, mundo, "Q-RECHAZADA", estado="rechazada")

        grupos = await admin._leer_cola()

        assert [g["nombre"] for g in grupos] == ["tijeras", "uniforme", "nuevo: aserrin colores"]
        tijeras = grupos[0]
        assert (tijeras["codigo"], tijeras["demanda"], tijeras["es_nuevo"]) == ("C002", 50, False)
        assert tijeras["concepto_id"] == mundo.tijeras.id.hex
        # Por nivel sugerido (economico, confiable, premium) y luego por precio.
        assert [p["id_corto"] for p in tijeras["propuestas"]] == [
            barata.id.hex[:8],
            media.id.hex[:8],
            cara.id.hex[:8],
        ]
        primera = tijeras["propuestas"][0]
        assert primera["nombre"] == "Tijeras Escolares Ficticias Q-BARATA"
        assert (primera["precio"], primera["nivel_sugerido"], primera["tienda"]) == (
            300000,
            "economico",
            "Exito",
        )
        assert primera["puntaje"] == pytest.approx(0.6)
        assert primera["origen"] == "scraper"
        creado = grupos[2]
        assert (creado["codigo"], creado["concepto_id"], creado["es_nuevo"], creado["demanda"]) == (
            None,
            None,
            True,
            0,
        )
        assert [p["id_corto"] for p in creado["propuestas"]] == [nuevo.id.hex[:8]]
        assert len(grupos) == 3  # la rechazada no vuelve a la cola

    async def test_sin_pendientes_la_cola_esta_vacia(self, bd):
        _sembrar(bd)
        assert await admin._leer_cola() == []


# ---------------------------------------------------------------------------
# Editar
# ---------------------------------------------------------------------------


class TestEditarProducto:
    async def _editar(self, producto, **kw):  # noqa: ANN001, ANN202
        base = {"nombre": None, "nivel": None, "imagen_url": None, "precio_centavos": None}
        base.update(kw)
        return await admin._editar_producto(producto.id.hex, **base)

    async def test_cambia_solo_lo_que_llega(self, bd):
        mundo = _sembrar(bd)

        ok, mensaje = await self._editar(mundo.cuaderno_eco, nombre="Cuaderno Corregido", nivel="premium")

        assert (ok, mensaje) == (True, "Producto actualizado.")
        p = _refrescar(bd, bd.get(ProductoCanonico, mundo.cuaderno_eco.id))
        assert (p.nombre, p.nivel) == ("Cuaderno Corregido", "premium")
        assert p.concepto_id == mundo.cuaderno.id
        assert p.sku_interno == "SKU-C1"  # el SKU interno no se toca jamas

    async def test_una_cadena_vacia_borra_a_proposito_y_none_no_toca(self, bd):
        mundo = _sembrar(bd)
        mundo.cuaderno_eco.imagen_url = "https://img.example.test/uno.jpg"
        mundo.cuaderno_eco.marca = "Marca Ficticia"
        bd.commit()

        await self._editar(mundo.cuaderno_eco)  # nada llega: nada cambia
        p = _refrescar(bd, bd.get(ProductoCanonico, mundo.cuaderno_eco.id))
        assert (p.imagen_url, p.marca) == ("https://img.example.test/uno.jpg", "Marca Ficticia")

        await self._editar(mundo.cuaderno_eco, imagen_url="", marca="")
        p = _refrescar(bd, bd.get(ProductoCanonico, mundo.cuaderno_eco.id))
        assert (p.imagen_url, p.marca) == (None, None)

    async def test_los_atributos_se_reemplazan_enteros_y_un_dict_vacio_los_vacia(self, bd):
        mundo = _sembrar(bd)
        mundo.cuaderno_eco.atributos = {"hojas": 100, "material": "papel"}
        bd.commit()

        await self._editar(mundo.cuaderno_eco, atributos={"hojas": "80"})
        p = _refrescar(bd, bd.get(ProductoCanonico, mundo.cuaderno_eco.id))
        assert p.atributos == {"hojas": "80"}

        await self._editar(mundo.cuaderno_eco, atributos={})
        p = _refrescar(bd, bd.get(ProductoCanonico, mundo.cuaderno_eco.id))
        assert p.atributos == {}

    async def test_reasignar_el_concepto_mueve_el_producto_y_no_toca_sus_ofertas(self, bd):
        mundo = _sembrar(bd)

        ok, _ = await self._editar(mundo.cuaderno_eco, concepto_id=mundo.tijeras.id.hex)

        assert ok
        p = _refrescar(bd, bd.get(ProductoCanonico, mundo.cuaderno_eco.id))
        assert p.concepto_id == mundo.tijeras.id
        assert _contar(bd, OfertaTienda) == 4

    async def test_un_concepto_inexistente_o_inactivo_se_rechaza_sin_escribir_nada(self, bd):
        mundo = _sembrar(bd)
        mundo.uniforme.activo = False
        bd.commit()

        for concepto_id in (uuid.uuid4().hex, mundo.uniforme.id.hex):
            ok, mensaje = await self._editar(
                mundo.cuaderno_eco, nombre="No debe quedar", concepto_id=concepto_id, precio_centavos=1
            )
            assert (ok, mensaje) == (False, "Ese concepto no existe o no está activo.")

        p = _refrescar(bd, bd.get(ProductoCanonico, mundo.cuaderno_eco.id))
        assert (p.nombre, p.concepto_id) == ("Cuaderno Ficticio Uno", mundo.cuaderno.id)
        assert _valores(bd, mundo.of_cuaderno)[-1] == (500000, True)

    async def test_un_producto_inexistente_o_retirado_no_se_edita(self, bd):
        mundo = _sembrar(bd)
        for producto_id in (uuid.uuid4().hex, mundo.cuaderno_retirado.id.hex):
            ok, mensaje = await admin._editar_producto(
                producto_id, nombre="Nuevo", nivel=None, imagen_url=None, precio_centavos=100
            )
            assert (ok, mensaje) == (False, "No encontré ese producto.")
        p = _refrescar(bd, bd.get(ProductoCanonico, mundo.cuaderno_retirado.id))
        assert p.nombre == "Cuaderno Retirado"

    async def test_el_precio_vigente_de_las_ofertas_activas_pasa_a_ser_el_nuevo(self, bd):
        mundo = _sembrar(bd)

        await self._editar(mundo.tijera, precio_centavos=950000)

        assert _valores(bd, mundo.of_tijera) == [(950000, True)]
        assert _valores(bd, mundo.of_tijera_inactiva) == [(700000, True)]  # la oferta inactiva no se toca

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-08: corregir el precio reescribe TODOS los tramos de precio_oferta, historia "
            "incluida (admin.py:366-373 sin 'vigente_hasta IS NULL'), contra 'un tramo de precio con "
            "vigencia, no una columna que se sobreescribe' (modelos/oferta.py:153)"
        ),
    )
    async def test_corregir_el_precio_no_reescribe_la_historia_de_precios(self, bd):
        mundo = _sembrar(bd)

        await self._editar(mundo.cuaderno_eco, precio_centavos=950000)

        assert _valores(bd, mundo.of_cuaderno) == [(400000, False), (950000, True)]


# ---------------------------------------------------------------------------
# Borrar, fijar, descartar
# ---------------------------------------------------------------------------


class TestBorrarProducto:
    async def test_se_lleva_sus_precios_ofertas_y_la_propuesta_aprobada_y_solo_a_el(self, bd):
        mundo = _sembrar(bd)
        borrado, oferta_borrada = mundo.cuaderno_eco.id, mundo.of_cuaderno.id
        conservado, otra_id = mundo.cuaderno_conf.id, None
        _propuesta(bd, mundo, "Q-APROBADA", estado="aprobada", producto_canonico_id=borrado)
        otra_id = _propuesta(bd, mundo, "Q-OTRA").id

        ok, mensaje = await admin._borrar_producto(borrado.hex)

        assert (ok, mensaje) == (True, "Producto borrado del catálogo.")
        bd.rollback()
        bd.expunge_all()
        assert bd.get(ProductoCanonico, borrado) is None
        sin_precios = (
            select(func.count()).select_from(PrecioOferta).where(PrecioOferta.oferta_id == oferta_borrada)
        )
        assert bd.scalar(sin_precios) == 0
        assert bd.get(OfertaTienda, oferta_borrada) is None
        assert [p.referencia_externa for p in bd.scalars(select(PropuestaProducto))] == ["Q-OTRA"]
        # El resto del catalogo sigue donde estaba.
        assert bd.get(ProductoCanonico, conservado) is not None
        assert _contar(bd, OfertaTienda) == 3
        assert _contar(bd, PrecioOferta) == 3
        assert bd.get(PropuestaProducto, otra_id) is not None

    async def test_un_producto_que_no_existe_no_borra_nada(self, bd):
        _sembrar(bd)
        assert await admin._borrar_producto(uuid.uuid4().hex) == (False, "No encontré ese producto.")
        assert _contar(bd, ProductoCanonico) == 4

    async def test_tambien_se_puede_borrar_uno_retirado(self, bd):
        """Retirado (inactivo) no es borrado: `volcar` lo exportaria, asi que quitarlo es borrarlo."""
        mundo = _sembrar(bd)
        ok, _ = await admin._borrar_producto(mundo.cuaderno_retirado.id.hex)
        assert ok
        assert _contar(bd, ProductoCanonico) == 3


class TestFijar:
    async def test_el_empaque_se_fija_y_dice_cuantas_filas_toco(self, bd):
        mundo = _sembrar(bd)
        assert await admin._fijar_columna_producto(str(mundo.tijera.id), unidades_por_empaque=12) == 1
        p = _refrescar(bd, bd.get(ProductoCanonico, mundo.tijera.id))
        assert p.unidades_por_empaque == 12
        assert await admin._fijar_columna_producto(str(uuid.uuid4()), unidades_por_empaque=3) == 0

    async def test_el_tipo_de_un_concepto_se_fija(self, bd):
        mundo = _sembrar(bd)
        assert await admin._fijar_tipo_concepto(str(mundo.uniforme.id), "no_comprar") == 1
        assert _refrescar(bd, bd.get(Concepto, mundo.uniforme.id)).tipo_item == "no_comprar"
        assert await admin._fijar_tipo_concepto(str(uuid.uuid4()), "no_comprar") == 0


class TestNoSurtirConcepto:
    async def test_marca_el_concepto_y_descarta_solo_sus_pendientes(self, bd):
        mundo = _sembrar(bd)
        pendiente_a = _propuesta(bd, mundo, "Q1")
        pendiente_b = _propuesta(bd, mundo, "Q2")
        aprobada = _propuesta(bd, mundo, "Q3", estado="aprobada", producto_canonico_id=mundo.tijera.id)
        de_otro = _propuesta(bd, mundo, "Q4", concepto_id=mundo.uniforme.id)

        ok, mensaje = await admin._no_surtir_concepto(str(mundo.tijeras.id))

        assert (ok, mensaje) == (True, "Concepto marcado no_comprar; 2 candidatos descartados.")
        bd.rollback()
        bd.expire_all()
        assert bd.get(Concepto, mundo.tijeras.id).tipo_item == "no_comprar"
        for descartada in (pendiente_a, pendiente_b):
            actual = bd.get(PropuestaProducto, descartada.id)
            assert (actual.estado, actual.motivo) == ("rechazada", "concepto no_comprar")
            assert actual.resuelta_en is not None
        assert bd.get(PropuestaProducto, aprobada.id).estado == "aprobada"
        assert bd.get(PropuestaProducto, de_otro.id).estado == "pendiente"
        assert bd.get(Concepto, mundo.uniforme.id).tipo_item == "util"

    async def test_un_concepto_que_no_existe_no_cambia_nada(self, bd):
        mundo = _sembrar(bd)
        pendiente = _propuesta(bd, mundo, "Q1")
        assert await admin._no_surtir_concepto(str(uuid.uuid4())) == (False, "No encontré ese concepto.")
        assert _refrescar(bd, bd.get(PropuestaProducto, pendiente.id)).estado == "pendiente"


class TestBusquedaPorId:
    async def test_concepto_por_id(self, bd):
        mundo = _sembrar(bd)
        assert await admin._concepto_por_id(str(mundo.tijeras.id)) == (mundo.tijeras.id, "tijeras")
        assert await admin._concepto_por_id(str(uuid.uuid4())) is None

    async def test_tienda_por_slug(self, bd):
        mundo = _sembrar(bd)
        assert await admin._tienda_por_slug("exito") == mundo.exito.id
        assert await admin._tienda_por_slug("no-existe") is None


# ---------------------------------------------------------------------------
# Candidatos y altas
# ---------------------------------------------------------------------------


class TestBuscarCandidatos:
    def test_filtra_lo_que_no_coincide_lo_agotado_y_lo_sin_precio_y_ordena_por_precio(self, monkeypatch):
        respuestas = {
            "exito": [
                _oferta_tienda("A", 9000, nombre="Tijeras Escolares Caras"),
                _oferta_tienda("B", 4000, nombre="Tijeras Escolares Agotadas", disponible=False),
                _oferta_tienda("C", 0, nombre="Tijeras Escolares Sin Precio"),
                _oferta_tienda("D", 3000, nombre="Cuchillo De Cocina"),  # no contiene lo pedido
            ],
            "panamericana": [
                _oferta_tienda("E", 5000, nombre="Tijeras Escolares Baratas", tienda="panamericana")
            ],
            "grancentral": [],
        }
        consultadas: list[str] = []

        def buscar(slug: str, consulta: str, *_a: Any) -> list[Oferta]:
            consultadas.append(slug)
            return respuestas[slug]

        monkeypatch.setattr(admin.tiendas, "buscar", buscar)

        candidatos = admin.buscar_candidatos("tijeras escolares")

        assert consultadas == ["exito", "panamericana", "grancentral"]
        assert [(slug, o.sku) for slug, o in candidatos] == [("panamericana", "E"), ("exito", "A")]


class TestAgregarUtil:
    async def test_nace_un_producto_con_oferta_y_precio_en_el_nivel_elegido(self, bd):
        mundo = _sembrar(bd)

        ok, mensaje = await admin.agregar_util(
            mundo.tijeras.id.hex, "exito", _oferta_tienda("T9", 12000), "premium"
        )

        assert (ok, mensaje) == (True, "Agregado a tijeras: Tijeras Escolares Candidatas (premium).")
        bd.rollback()
        producto = bd.scalar(select(ProductoCanonico).where(ProductoCanonico.sku_interno == "TK-REV-T9"))
        assert producto.concepto_id == mundo.tijeras.id
        assert producto.nivel == "premium"
        assert producto.curado_por == AGENTE_FIRECRAWL
        oferta = bd.scalar(select(OfertaTienda).where(OfertaTienda.producto_canonico_id == producto.id))
        assert oferta.tienda_id == mundo.exito.id
        precio = bd.scalar(select(PrecioOferta).where(PrecioOferta.oferta_id == oferta.id))
        assert precio.valor_centavos == 1200000  # pesos a centavos
        propuesta = bd.scalar(select(PropuestaProducto).where(PropuestaProducto.referencia_externa == "T9"))
        assert (propuesta.estado, propuesta.origen, propuesta.version_lista_id) == (
            "aprobada",
            "manual",
            None,
        )

    async def test_una_tienda_o_un_concepto_desconocidos_no_crean_nada(self, bd):
        mundo = _sembrar(bd)
        assert await admin.agregar_util(
            mundo.tijeras.id.hex, "libreria-x", _oferta_tienda(), "economico"
        ) == (
            False,
            "No conozco la tienda 'libreria-x'.",
        )
        assert await admin.agregar_util(uuid.uuid4().hex, "exito", _oferta_tienda(), "economico") == (
            False,
            "Ese concepto ya no existe.",
        )
        assert _contar(bd, PropuestaProducto) == 0
        assert _contar(bd, ProductoCanonico) == 4

    async def test_agregar_dos_veces_el_mismo_candidato_no_duplica_nada(self, bd):
        mundo = _sembrar(bd)
        await admin.agregar_util(mundo.tijeras.id.hex, "exito", _oferta_tienda("T9"), "economico")

        ok, mensaje = await admin.agregar_util(
            mundo.tijeras.id.hex, "exito", _oferta_tienda("T9"), "economico"
        )

        assert ok is False
        assert "no se pudo aprobar" in mensaje
        assert _contar(bd, ProductoCanonico) == 5
        assert _contar(bd, PropuestaProducto) == 1

    async def test_un_ean_que_no_es_un_ean_no_llega_a_la_propuesta(self, bd):
        mundo = _sembrar(bd)
        await admin.agregar_util(
            mundo.tijeras.id.hex, "exito", _oferta_tienda("T9", ean="SKU-INTERNO"), "economico"
        )
        bd.rollback()
        assert bd.scalar(select(PropuestaProducto.ean)) is None


class TestAgregarLibro:
    async def test_un_isbn_con_guiones_se_normaliza_y_nace_el_producto(self, bd):
        mundo = _sembrar(bd)

        ok, mensaje = await admin.agregar_libro(
            mundo.tijeras.id.hex, "978-958-07-1472-9", "Libro Ficticio", 52000, "panamericana", "confiable"
        )

        assert (ok, mensaje) == (True, "Libro agregado a tijeras: Libro Ficticio.")
        bd.rollback()
        producto = bd.scalar(select(ProductoCanonico).where(ProductoCanonico.ean == ISBN_VALIDO))
        assert producto.nombre == "Libro Ficticio"
        assert producto.sku_interno == f"TK-REV-{ISBN_VALIDO}"
        oferta = bd.scalar(select(OfertaTienda).where(OfertaTienda.producto_canonico_id == producto.id))
        assert oferta.tienda_id == mundo.panam.id
        assert (
            bd.scalar(select(PrecioOferta.valor_centavos).where(PrecioOferta.oferta_id == oferta.id))
            == 5200000
        )

    @pytest.mark.parametrize(
        ("isbn", "tienda", "concepto_existe", "mensaje"),
        [
            ("9789580714728", "exito", True, "no pasa el digito de control"),
            ("", "exito", True, "no pasa el digito de control"),
            (ISBN_VALIDO, "libreria-x", True, "No conozco la tienda 'libreria-x'."),
            (ISBN_VALIDO, "exito", False, "Ese concepto ya no existe."),
        ],
    )
    async def test_lo_malo_se_rechaza_antes_de_encolar(self, bd, isbn, tienda, concepto_existe, mensaje):
        """Un ISBN mal copiado entra sin ruido y el dia de la compra resulta ser otra edicion."""
        mundo = _sembrar(bd)
        concepto = mundo.tijeras.id.hex if concepto_existe else uuid.uuid4().hex

        ok, texto = await admin.agregar_libro(concepto, isbn, "Libro", 52000, tienda, "confiable")

        assert ok is False and mensaje in texto
        assert _contar(bd, PropuestaProducto) == 0
        assert _contar(bd, ProductoCanonico) == 4


class TestDesdeLaCola:
    async def test_aprobar_corrige_el_nivel_sugerido(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, "Q1", nivel_sugerido="confiable")

        assert await admin.aprobar_propuesta(p.id.hex[:8], "economico") == (True, "Aprobada como economico.")

        bd.rollback()
        assert (
            bd.scalar(select(ProductoCanonico.nivel).where(ProductoCanonico.sku_interno == "TK-REV-Q1"))
            == "economico"
        )

    async def test_aprobar_algo_ya_resuelto_o_inexistente_dice_que_no_se_pudo(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, "Q1", estado="rechazada")
        esperado = (False, "No se pudo aprobar. Puede que ya esté resuelta o le falte concepto.")
        assert await admin.aprobar_propuesta(p.id.hex[:8], "economico") == esperado
        assert await admin.aprobar_propuesta("ffffffff", "economico") == esperado

    async def test_aprobar_sin_concepto_no_se_puede(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, "Q1", concepto_id=None, concepto_sugerido="aserrin colores")
        ok, _ = await admin.aprobar_propuesta(p.id.hex[:8], "economico")
        assert ok is False
        assert _contar(bd, ProductoCanonico) == 4

    async def test_rechazar_descarta_el_candidato_y_deja_abierto_el_concepto(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, "Q1")

        assert await admin.rechazar_propuesta(p.id.hex[:8], "es otra cosa", False) == (
            True,
            "Candidato descartado.",
        )

        bd.rollback()
        assert (bd.get(PropuestaProducto, p.id).estado, bd.get(PropuestaProducto, p.id).motivo) == (
            "rechazada",
            "es otra cosa",
        )
        assert bd.get(Concepto, mundo.tijeras.id).tipo_item == "util"

    async def test_rechazar_con_no_surtir_cierra_el_concepto(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, "Q1")
        assert await admin.rechazar_propuesta(p.id.hex[:8], None, True) == (
            True,
            "Concepto marcado no_comprar.",
        )
        assert _refrescar(bd, bd.get(Concepto, mundo.tijeras.id)).tipo_item == "no_comprar"

    async def test_rechazar_algo_ya_resuelto_dice_que_no_se_pudo(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, "Q1", estado="rechazada")
        assert await admin.rechazar_propuesta(p.id.hex[:8], None, False) == (
            False,
            "No se pudo rechazar. Puede que ya esté resuelta.",
        )


# ---------------------------------------------------------------------------
# HTML: ramas que test_admin no pinta
# ---------------------------------------------------------------------------


def _prod_html(**kw) -> dict[str, Any]:
    base = {
        "id": "p1",
        "nombre": "Cuaderno Ficticio",
        "nivel": "economico",
        "imagen_url": None,
        "personaje": None,
        "marca": None,
        "atributos": {},
        "unidad_base": None,
        "unidades_por_empaque": None,
        "quality_score": 0.85,
        "tienda": None,
        "url": None,
        "precio": None,
    }
    base.update(kw)
    return base


def _concepto_html(**kw) -> dict[str, Any]:
    base = {
        "id": "c1",
        "codigo": "C001",
        "nombre": "cuaderno",
        "tipo_item": "util",
        "demanda": 4,
        "sinonimos": [],
        "atributos_clave": [],
        "productos": [],
    }
    base.update(kw)
    return base


class TestHtml:
    def test_un_producto_sin_foto_ni_precio_ni_tienda_se_pinta_con_lo_que_falta_dicho(self):
        tarjeta = admin._tarjeta(_prod_html())
        assert "sin foto" in tarjeta
        assert "sin precio" in tarjeta
        assert "sin tienda" in tarjeta
        assert "sin atributos" in tarjeta
        assert 'value="1"' in tarjeta  # empaque por omision

    def test_el_personaje_la_marca_y_el_enlace_aparecen_cuando_existen(self):
        tarjeta = admin._tarjeta(
            _prod_html(
                personaje="Frozen", marca="Marca Ficticia", url="https://x.example.test/p", precio=650000
            )
        )
        assert "Frozen" in tarjeta
        assert '<span class="marca">Marca Ficticia</span>' in tarjeta
        assert '<a href="https://x.example.test/p"' in tarjeta
        assert "$6.500" in tarjeta

    def test_el_nombre_de_un_producto_no_inyecta_html(self):
        tarjeta = admin._tarjeta(_prod_html(nombre="<script>alert(1)</script>", marca='"><img src=x>'))
        assert "<script>" not in tarjeta
        assert "&lt;script&gt;" in tarjeta
        assert '"><img' not in tarjeta

    def test_un_concepto_vacio_se_marca_y_los_de_otro_tipo_llevan_su_pastilla(self):
        libro = admin._bloque_concepto(_concepto_html(tipo_item="libro_libre"))
        assert "sin productos" in libro and "pill libro" in libro and "nada que ofrecer" in libro
        descartado = admin._bloque_concepto(_concepto_html(tipo_item="no_comprar"))
        assert "no se surte" in descartado
        assert "destacado" not in descartado  # lo que no se surte no pide atencion

    def test_un_producto_sin_puntaje_marca_al_concepto_como_por_revisar(self):
        bloque = admin._bloque_concepto(_concepto_html(productos=[_prod_html(quality_score=None)]))
        assert "tiene sin revisar" in bloque
        assert 'data-revisar="1"' in bloque


# ---------------------------------------------------------------------------
# Servidor HTTP (sin abrir un puerto)
# ---------------------------------------------------------------------------


class _Respuesta:
    def __init__(self, bruto: bytes) -> None:
        cabeza, _, self.cuerpo = bruto.partition(b"\r\n\r\n")
        self.codigo = int(cabeza.split(b" ", 2)[1])
        self.cabecera = cabeza.decode("latin-1")

    def json(self) -> dict[str, Any]:
        return json.loads(self.cuerpo)

    @property
    def texto(self) -> str:
        return self.cuerpo.decode("utf-8")


def _http(metodo: str, ruta: str, cuerpo: Any = None, *, crudo: bytes | None = None) -> _Respuesta:
    """Invoca `do_GET`/`do_POST` del manejador con buffers en memoria: ni sockets ni hilos."""
    datos = crudo if crudo is not None else (json.dumps(cuerpo).encode() if cuerpo is not None else b"")
    manejador = object.__new__(admin._Manejador)
    manejador.rfile = io.BytesIO(datos)
    manejador.wfile = io.BytesIO()
    manejador.headers = Message()
    manejador.headers["Content-Length"] = str(len(datos))
    manejador.path = ruta
    manejador.command = metodo
    manejador.request_version = "HTTP/1.1"
    manejador.requestline = f"{metodo} {ruta} HTTP/1.1"
    manejador.client_address = ("127.0.0.1", 0)
    getattr(manejador, f"do_{metodo}")()
    return _Respuesta(manejador.wfile.getvalue())


class TestRutas:
    def test_la_cola_se_sirve_como_html(self, bd):
        mundo = _sembrar(bd)
        _propuesta(bd, mundo, "Q1")

        respuesta = _http("GET", "/cola")

        assert respuesta.codigo == 200
        assert "text/html" in respuesta.cabecera
        assert "Tijeras Escolares Ficticias Q1" in respuesta.texto

    def test_la_pagina_principal_se_pinta_con_lo_que_lee(self, monkeypatch):
        filas = [_fila_leer("A", pid="a1", nombre="Cuaderno Ficticio <b>Uno</b>")]
        monkeypatch.setattr("tukit_comun.bd.crear_motor", lambda _s: _MotorFalso([filas, 2, 0]))

        for ruta in ("/", "/index.html"):
            respuesta = _http("GET", ruta)
            assert respuesta.codigo == 200
            assert "Cuaderno Ficticio &lt;b&gt;Uno&lt;/b&gt;" in respuesta.texto  # escapado, no inyectado

    def test_una_ruta_que_no_existe_responde_404_en_json(self):
        for metodo in ("GET", "POST"):
            respuesta = _http(metodo, "/no-existe")
            assert (respuesta.codigo, respuesta.json()["ok"]) == (404, False)

    def test_la_cabecera_declara_utf8_y_el_largo_exacto(self):
        respuesta = _http("GET", "/no-existe")
        assert "application/json; charset=utf-8" in respuesta.cabecera
        assert f"Content-Length: {len(respuesta.cuerpo)}" in respuesta.cabecera

    def test_un_cuerpo_que_no_es_json_se_trata_como_vacio(self):
        respuesta = _http("POST", "/util-buscar", crudo=b"esto no es json")
        assert (respuesta.codigo, respuesta.json()["mensaje"]) == (400, "falta la consulta")

    def test_un_error_inesperado_responde_500_y_no_tumba_el_servidor(self, monkeypatch):
        async def explota(_id: str):
            raise RuntimeError("se cayo la base")

        monkeypatch.setattr(admin, "_borrar_producto", explota)

        respuesta = _http("POST", "/borrar", {"producto_id": "abc"})

        assert respuesta.codigo == 500
        assert respuesta.json() == {"ok": False, "mensaje": "error: se cayo la base"}
        assert _http("GET", "/no-existe").codigo == 404  # el siguiente request se atiende

    def test_un_id_que_no_es_uuid_no_es_un_exito(self, bd):
        """Quien manda basura recibe un error en JSON, no un 200 ni un traceback."""
        _sembrar(bd)
        for ruta, cuerpo in (
            ("/empaque", {"producto_id": "no-es-uuid", "unidades": 3}),
            ("/descartar", {"concepto_id": "no-es-uuid"}),
        ):
            respuesta = _http("POST", ruta, cuerpo)
            assert respuesta.codigo >= 400
            assert respuesta.json()["ok"] is False


class TestRutasDeCuraduria:
    def test_buscar_util_exige_consulta_y_devuelve_los_candidatos_resumidos(self, monkeypatch):
        monkeypatch.setattr(
            admin.tiendas,
            "buscar",
            lambda slug, _c, *_a: (
                [_oferta_tienda("A", 4000, nombre="Tijeras Escolares " + "x" * 100)]
                if slug == "exito"
                else []
            ),
        )

        vacio = _http("POST", "/util-buscar", {"consulta": "   "})
        respuesta = _http("POST", "/util-buscar", {"consulta": "tijeras escolares"})

        assert vacio.codigo == 400
        (candidato,) = respuesta.json()["candidatos"]
        assert candidato["slug"] == "exito" and candidato["sku"] == "A" and candidato["precio"] == 4000
        assert len(candidato["nombre"]) == 80  # el nombre se recorta para la lista

    def test_agregar_util_toma_la_oferta_de_la_tienda_y_no_el_precio_del_navegador(self, bd, monkeypatch):
        mundo = _sembrar(bd)
        monkeypatch.setattr(
            admin.tiendas,
            "buscar",
            lambda slug, _c, *_a: [_oferta_tienda("T9", 12000)] if slug == "exito" else [],
        )

        respuesta = _http(
            "POST",
            "/util",
            {
                "consulta": "tijeras escolares",
                "slug": "exito",
                "sku": "T9",
                "nivel": "economico",
                "concepto_id": mundo.tijeras.id.hex,
                "precio": 1,  # el navegador miente: se ignora
            },
        )

        assert (respuesta.codigo, respuesta.json()["ok"]) == (200, True)
        bd.rollback()
        assert (
            bd.scalar(
                select(PropuestaProducto.precio_centavos).where(PropuestaProducto.referencia_externa == "T9")
            )
            == 1200000
        )

    def test_agregar_un_util_que_la_tienda_ya_no_devuelve_responde_422(self, bd, monkeypatch):
        mundo = _sembrar(bd)
        monkeypatch.setattr(admin.tiendas, "buscar", lambda *_a: [])

        respuesta = _http(
            "POST",
            "/util",
            {"consulta": "tijeras", "slug": "exito", "sku": "T9", "concepto_id": mundo.tijeras.id.hex},
        )

        assert respuesta.codigo == 422
        assert "ya no está disponible" in respuesta.json()["mensaje"]
        assert _contar(bd, PropuestaProducto) == 0

    def test_agregar_libro_valida_el_precio_antes_de_tocar_la_base(self, bd):
        mundo = _sembrar(bd)
        base = {"concepto_id": mundo.tijeras.id.hex, "isbn": ISBN_VALIDO, "titulo": "Libro Ficticio"}
        for precio in (None, 0, -5, "mucho"):
            respuesta = _http("POST", "/libro", {**base, "precio": precio})
            assert respuesta.codigo == 400
            assert "entero positivo" in respuesta.json()["mensaje"]
        assert _contar(bd, PropuestaProducto) == 0

    def test_agregar_libro_usa_panamericana_y_confiable_por_omision(self, bd):
        mundo = _sembrar(bd)

        respuesta = _http(
            "POST",
            "/libro",
            {
                "concepto_id": mundo.tijeras.id.hex,
                "isbn": ISBN_VALIDO,
                "titulo": " Libro Ficticio ",
                "precio": "52000",
            },
        )

        assert (respuesta.codigo, respuesta.json()["mensaje"]) == (
            200,
            "Libro agregado a tijeras: Libro Ficticio.",
        )
        bd.rollback()
        propuesta = bd.scalar(select(PropuestaProducto))
        assert propuesta.tienda_id == mundo.panam.id
        assert propuesta.nivel_sugerido == "confiable"

    def test_agregar_libro_con_isbn_malo_responde_422_con_el_motivo(self, bd):
        mundo = _sembrar(bd)
        respuesta = _http(
            "POST",
            "/libro",
            {"concepto_id": mundo.tijeras.id.hex, "isbn": "9789580714728", "titulo": "Libro", "precio": 1000},
        )
        assert respuesta.codigo == 422
        assert "digito de control" in respuesta.json()["mensaje"]

    def test_descartar_un_concepto_lo_marca_y_uno_inexistente_es_404(self, bd):
        mundo = _sembrar(bd)

        ok = _http("POST", "/descartar", {"concepto_id": str(mundo.uniforme.id)})
        falta = _http("POST", "/descartar", {"concepto_id": str(uuid.uuid4())})

        assert (ok.codigo, falta.codigo) == (200, 404)
        assert _refrescar(bd, bd.get(Concepto, mundo.uniforme.id)).tipo_item == "no_comprar"

    def test_editar_pide_el_producto_y_valida_el_precio_en_pesos(self, bd):
        mundo = _sembrar(bd)
        producto = mundo.tijera.id.hex
        assert _http("POST", "/editar", {"nombre": "Sin producto"}).codigo == 400
        for precio in ("mucho", 0, -3):
            respuesta = _http("POST", "/editar", {"producto_id": producto, "precio": precio})
            assert respuesta.codigo == 400
        malos = _http("POST", "/editar", {"producto_id": producto, "atributos": ["no", "es", "un", "objeto"]})
        assert malos.codigo == 400
        assert _valores(bd, mundo.of_tijera) == [(800000, True)]  # nada se escribio

    def test_editar_convierte_pesos_a_centavos_y_los_atributos_a_texto(self, bd):
        mundo = _sembrar(bd)

        respuesta = _http(
            "POST",
            "/editar",
            {
                "producto_id": mundo.tijera.id.hex,
                "nombre": "  Tijeras Corregidas  ",
                "precio": "9500",
                "atributos": {"hojas": 100},
            },
        )

        assert (respuesta.codigo, respuesta.json()["ok"]) == (200, True)
        p = _refrescar(bd, bd.get(ProductoCanonico, mundo.tijera.id))
        assert p.nombre == "Tijeras Corregidas"
        assert p.atributos == {"hojas": "100"}
        assert _valores(bd, mundo.of_tijera) == [(950000, True)]

    def test_editar_un_producto_inexistente_es_404(self, bd):
        _sembrar(bd)
        respuesta = _http("POST", "/editar", {"producto_id": uuid.uuid4().hex, "nombre": "X"})
        assert (respuesta.codigo, respuesta.json()["mensaje"]) == (404, "No encontré ese producto.")

    def test_borrar(self, bd):
        mundo = _sembrar(bd)
        assert _http("POST", "/borrar", {}).codigo == 400
        assert _http("POST", "/borrar", {"producto_id": uuid.uuid4().hex}).codigo == 404
        assert _http("POST", "/borrar", {"producto_id": mundo.tijera.id.hex}).codigo == 200
        assert _contar(bd, ProductoCanonico) == 3

    def test_empaque_exige_un_entero_de_al_menos_uno(self, bd):
        mundo = _sembrar(bd)
        for unidades in (0, -1, "docena", None):
            respuesta = _http("POST", "/empaque", {"producto_id": str(mundo.tijera.id), "unidades": unidades})
            assert (respuesta.codigo, respuesta.json()["mensaje"]) == (400, "El empaque es un entero >= 1.")
        assert _refrescar(bd, bd.get(ProductoCanonico, mundo.tijera.id)).unidades_por_empaque == 1

    def test_empaque_se_fija_y_un_producto_inexistente_es_404(self, bd):
        mundo = _sembrar(bd)
        ok = _http("POST", "/empaque", {"producto_id": str(mundo.tijera.id), "unidades": "12"})
        falta = _http("POST", "/empaque", {"producto_id": str(uuid.uuid4()), "unidades": 12})
        assert (ok.codigo, falta.codigo) == (200, 404)
        assert _refrescar(bd, bd.get(ProductoCanonico, mundo.tijera.id)).unidades_por_empaque == 12

    def test_volcar_corre_el_volcado_de_verdad_y_no_el_ensayo(self, monkeypatch):
        llamadas: list[dict[str, Any]] = []

        async def volcar_falso(**kw: Any) -> None:
            llamadas.append(kw)

        monkeypatch.setattr(admin, "volcar_principal", volcar_falso)

        respuesta = _http("POST", "/volcar", {})

        assert respuesta.codigo == 200
        assert llamadas == [{"solo_ensayo": False}]

    def test_aprobar_desde_la_cola(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, "Q1")
        assert _http("POST", "/cola-aprobar", {"nivel": "premium"}).codigo == 400  # falta el id

        ok = _http("POST", "/cola-aprobar", {"id": p.id.hex[:8], "nivel": "premium"})
        repetida = _http("POST", "/cola-aprobar", {"id": p.id.hex[:8]})

        assert (ok.codigo, ok.json()["mensaje"]) == (200, "Aprobada como premium.")
        assert repetida.codigo == 422  # ya no esta pendiente

    def test_rechazar_un_candidato_desde_la_cola(self, bd):
        mundo = _sembrar(bd)
        p = _propuesta(bd, mundo, "Q1")
        assert _http("POST", "/cola-rechazar", {}).codigo == 400

        ok = _http("POST", "/cola-rechazar", {"id": p.id.hex[:8]})
        repetida = _http("POST", "/cola-rechazar", {"id": p.id.hex[:8]})

        assert (ok.codigo, ok.json()["mensaje"]) == (200, "Candidato descartado.")
        assert repetida.codigo == 422
        assert _refrescar(bd, bd.get(Concepto, mundo.tijeras.id)).tipo_item == "util"

    def test_rechazar_con_no_surtir_cierra_el_concepto_y_descarta_sus_pendientes(self, bd):
        mundo = _sembrar(bd)
        a, b = _propuesta(bd, mundo, "Q1"), _propuesta(bd, mundo, "Q2")
        assert _http("POST", "/cola-rechazar", {"no_surtir": True}).codigo == 400  # falta el concepto

        respuesta = _http("POST", "/cola-rechazar", {"no_surtir": True, "concepto_id": str(mundo.tijeras.id)})

        assert (respuesta.codigo, respuesta.json()["ok"]) == (200, True)
        bd.rollback()
        bd.expire_all()
        assert bd.get(Concepto, mundo.tijeras.id).tipo_item == "no_comprar"
        assert {bd.get(PropuestaProducto, x.id).estado for x in (a, b)} == {"rechazada"}

    def test_no_surtir_un_concepto_que_no_existe_es_422(self, bd):
        _sembrar(bd)
        respuesta = _http("POST", "/cola-rechazar", {"no_surtir": True, "concepto_id": str(uuid.uuid4())})
        assert respuesta.codigo == 422


# ---------------------------------------------------------------------------
# servir / main
# ---------------------------------------------------------------------------


class _ServidorFalso:
    creados: list[_ServidorFalso] = []  # noqa: RUF012

    def __init__(self, direccion: tuple[str, int], manejador: type) -> None:
        self.direccion, self.manejador = direccion, manejador
        self.cerrado = False
        _ServidorFalso.creados.append(self)

    def serve_forever(self) -> None:
        raise KeyboardInterrupt

    def server_close(self) -> None:
        self.cerrado = True


class TestServirYMain:
    @pytest.fixture(autouse=True)
    def _servidor_falso(self, monkeypatch: pytest.MonkeyPatch):
        _ServidorFalso.creados = []
        monkeypatch.setattr(admin, "ThreadingHTTPServer", _ServidorFalso)

    def test_escucha_solo_en_el_loopback_y_se_cierra_con_ctrl_c(self, capsys):
        """La consola no tiene autenticacion: lo unico que la protege es no salir de la maquina."""
        assert admin.servir(9123, False) == 0

        (servidor,) = _ServidorFalso.creados
        assert servidor.direccion == ("127.0.0.1", 9123)
        assert servidor.manejador is admin._Manejador
        assert servidor.cerrado is True
        salida = capsys.readouterr().out
        assert "http://127.0.0.1:9123/" in salida and "Listo." in salida

    def test_abrir_lanza_el_navegador_en_esa_direccion(self, monkeypatch):
        abiertas: list[str] = []
        monkeypatch.setattr("webbrowser.open", abiertas.append)
        admin.servir(9124, True)
        assert abiertas == ["http://127.0.0.1:9124/"]

    def test_sin_abrir_no_se_toca_el_navegador(self, monkeypatch):
        def no_debe_abrirse(_url: str) -> None:
            raise AssertionError("no se pidio abrir el navegador")

        monkeypatch.setattr("webbrowser.open", no_debe_abrirse)
        assert admin.servir(9125, False) == 0

    @pytest.mark.parametrize(
        ("argv", "esperado"),
        [([], (8000, False)), (["--puerto", "9001", "--abrir"], (9001, True))],
    )
    def test_main_pasa_el_puerto_y_la_bandera(self, monkeypatch, argv, esperado):
        recibido: list[tuple[int, bool]] = []
        monkeypatch.setattr(admin, "servir", lambda puerto, abrir: recibido.append((puerto, abrir)) or 5)
        monkeypatch.setattr("sys.argv", ["admin", *argv])

        assert admin.main() == 5
        assert recibido == [esperado]
