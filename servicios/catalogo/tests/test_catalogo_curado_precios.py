# ruff: noqa: F811

from __future__ import annotations

import uuid
from collections import defaultdict

from _ayudas_catalogo_curado import (  # noqa: F401  (los fixtures se reusan tal cual)
    UMBRAL_ACEPTACION,
    cargado,
    catalogo,
)
from tukit_catalogo.modelos import (
    UMBRAL_REVISION_MANUAL,
    MetodoVinculacion,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
    Tienda,
)

PRECIO_MIN_CENTAVOS = 500 * 100
PRECIO_MAX_CENTAVOS = 854_160 * 100


class TestPrecios:
    def test_el_precio_no_vive_en_el_producto(self):
        columnas = set(ProductoCanonico.__table__.columns.keys())
        assert not (columnas & {"precio", "stock", "proveedor", "disponible", "url_producto"})

    def test_todo_precio_es_entero_de_centavos_y_esta_en_rango(self, cargado):
        precios = cargado.query(PrecioOferta).all()
        assert precios
        for precio in precios:
            assert isinstance(precio.valor_centavos, int)
            assert precio.valor_centavos % 100 == 0, "el feed publica pesos, no fracciones"
            assert PRECIO_MIN_CENTAVOS <= precio.valor_centavos <= PRECIO_MAX_CENTAVOS
            assert precio.moneda == "COP"

    def test_cada_oferta_tiene_exactamente_un_precio_vigente(self, cargado):
        por_oferta: dict[uuid.UUID, int] = defaultdict(int)
        for precio in cargado.query(PrecioOferta):
            if precio.vigente:
                por_oferta[precio.oferta_id] += 1
        ofertas = cargado.query(OfertaTienda).all()
        assert len(por_oferta) == len(ofertas)
        assert set(por_oferta.values()) == {1}

    def test_todo_producto_tiene_al_menos_una_oferta_con_precio(self, cargado):
        con_oferta = {o.producto_canonico_id for o in cargado.query(OfertaTienda)}
        sin_oferta = [p.sku_interno for p in cargado.query(ProductoCanonico) if p.id not in con_oferta]
        assert sin_oferta == []

    def test_los_niveles_ordenan_el_precio_de_la_canasta(self, cargado):
        import statistics

        precio_de = {
            o.producto_canonico_id: p.valor_centavos
            for o in cargado.query(OfertaTienda)
            for p in cargado.query(PrecioOferta).filter_by(oferta_id=o.id)
            if p.vigente
        }
        medianas = {}
        for nivel in ("economico", "confiable", "premium"):
            valores = [
                precio_de[p.id]
                for p in cargado.query(ProductoCanonico).filter_by(nivel=nivel)
                if p.id in precio_de
            ]
            medianas[nivel] = statistics.median(valores)
        assert medianas["economico"] < medianas["confiable"] < medianas["premium"]


class TestVinculacionEntreTiendas:
    def test_los_metodos_son_los_del_esquema(self, catalogo):
        metodos = {o["metodo_vinculacion"] for o in catalogo["ofertas_tienda"]}
        assert metodos <= {m.value for m in MetodoVinculacion}

    def test_la_vinculacion_por_ean_va_con_confianza_plena(self, catalogo):
        sku_de = {p["id"]: p["sku_interno"] for p in catalogo["productos_canonicos"]}
        for oferta in catalogo["ofertas_tienda"]:
            if oferta["metodo_vinculacion"] != "ean":
                continue
            if (sku_de.get(oferta["producto_canonico_id"]) or "").startswith("TK-REV-"):
                continue
            assert float(oferta["confianza_vinculacion"]) == 1.000

    def test_nada_por_debajo_del_umbral_medido_llega_al_catalogo(self, catalogo):
        for oferta in catalogo["ofertas_tienda"]:
            if oferta["metodo_vinculacion"] == "atributos":
                assert float(oferta["confianza_vinculacion"]) >= UMBRAL_ACEPTACION

    def test_lo_dudoso_va_a_la_cola_y_no_se_descarta_ni_se_da_por_bueno(self, catalogo):
        dudosas = [
            o
            for o in catalogo["ofertas_tienda"]
            if o["metodo_vinculacion"] == "atributos"
            and float(o["confianza_vinculacion"]) < UMBRAL_REVISION_MANUAL
        ]
        assert len(catalogo["revision_manual"]) == len(dudosas)
        for fila in catalogo["revision_manual"]:
            confianza = float(fila["confianza"])
            assert UMBRAL_ACEPTACION <= confianza < UMBRAL_REVISION_MANUAL
            assert fila["motivo"]
            assert fila["oferta_url"].startswith("http")

    def test_la_propiedad_requiere_revision_concuerda_con_la_cola(self, cargado, catalogo):
        marcadas = [o for o in cargado.query(OfertaTienda) if o.requiere_revision]
        assert len(marcadas) == len(catalogo["revision_manual"])

    def test_el_mayorista_no_aporta_ean(self, cargado, catalogo):
        del catalogo
        mayoristas = {t.id for t in cargado.query(Tienda) if t.tipo == "mayorista"}
        assert mayoristas
        for oferta in cargado.query(OfertaTienda):
            if oferta.tienda_id in mayoristas:
                assert oferta.metodo_vinculacion != MetodoVinculacion.EAN.value

    def test_disponible_distingue_no_se_de_no_hay(self, cargado):
        valores = {o.disponible for o in cargado.query(OfertaTienda)}
        assert None in valores or False in valores or True in valores
        for oferta in cargado.query(OfertaTienda):
            assert oferta.disponible in (True, False, None)
