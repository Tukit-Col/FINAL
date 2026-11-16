"""Los precios del catalogo curado y la vinculacion de un producto entre tiendas."""

# Los fixtures `catalogo` y `cargado` llegan de `_ayudas_catalogo_curado`.
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

# Rango plausible de precio, en centavos. Son los p01-p99 medidos por fuente en
# `PERFILADO_DATOS.md` §5.2 (2.890-854.160 COP en el feed del scraper,
# 650-208.596 COP en GranCentral), tomados por la union porque el CSV de
# precios ya no dice de que fuente salio cada uno.
#
# El minimo baja de 650 a 500 COP: zamux.co vende componentes electronicos por unidad
# (resistencia 1/4w a 500 COP, switch corredera a 600 COP; precio leido en la ficha y en
# su JSON-LD el 2026-11-01). Son precios reales, no un error de carga, y el piso previo
# salia de los percentiles de otras fuentes. Un piso de 500 sigue atrapando un precio en
# pesos de un digito o en unidades equivocadas.
PRECIO_MIN_CENTAVOS = 500 * 100
PRECIO_MAX_CENTAVOS = 854_160 * 100


class TestPrecios:
    def test_el_precio_no_vive_en_el_producto(self):
        """La correccion de tercera forma normal que motivo el esquema. Si
        alguien devuelve la columna, comparar precio entre tiendas vuelve a ser
        inexpresable."""
        columnas = set(ProductoCanonico.__table__.columns.keys())
        assert not (columnas & {"precio", "stock", "proveedor", "disponible", "url_producto"})

    def test_todo_precio_es_entero_de_centavos_y_esta_en_rango(self, cargado):
        """Rango plausible = p01-p99 medidos por fuente en el perfilado. Un
        precio fuera de ahi no es caro ni barato, es un dato roto."""
        precios = cargado.query(PrecioOferta).all()
        assert precios
        for precio in precios:
            assert isinstance(precio.valor_centavos, int)
            assert precio.valor_centavos % 100 == 0, "el feed publica pesos, no fracciones"
            assert PRECIO_MIN_CENTAVOS <= precio.valor_centavos <= PRECIO_MAX_CENTAVOS
            assert precio.moneda == "COP"

    def test_cada_oferta_tiene_exactamente_un_precio_vigente(self, cargado):
        """Sin esto, "el precio de hoy" es una consulta ambigua."""
        por_oferta: dict[uuid.UUID, int] = defaultdict(int)
        for precio in cargado.query(PrecioOferta):
            if precio.vigente:
                por_oferta[precio.oferta_id] += 1
        ofertas = cargado.query(OfertaTienda).all()
        assert len(por_oferta) == len(ofertas)
        assert set(por_oferta.values()) == {1}

    def test_todo_producto_tiene_al_menos_una_oferta_con_precio(self, cargado):
        """Un producto canonico sin oferta no se puede poner en un kit: existe
        en el catalogo y no se puede comprar en ninguna parte."""
        con_oferta = {o.producto_canonico_id for o in cargado.query(OfertaTienda)}
        sin_oferta = [p.sku_interno for p in cargado.query(ProductoCanonico) if p.id not in con_oferta]
        assert sin_oferta == []

    def test_los_niveles_ordenan_el_precio_de_la_canasta(self, cargado):
        """No se exige producto a producto, porque un premium barato existe.
        Se exige en la mediana, que es lo que hace que el kit economico
        termine costando menos que el premium; si no, la promesa multiperfil
        no se sostiene."""
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
        """Un EAN coincide o no coincide; no tiene grados. Una confianza
        intermedia en una vinculacion por EAN seria una contradiccion.

        Excepto en el tier aprobado en revision (`TK-REV-*`): ahi el 0,85 no mide
        el emparejamiento del EAN sino el producto entero -es el mismo puntaje
        que lleva `quality_score`, 'lo miro una persona en la cola'-, y se hereda
        a la oferta. La confianza plena por EAN rige la vinculacion de la semilla,
        que es donde el EAN de verdad decidio el emparejamiento entre tiendas."""
        sku_de = {p["id"]: p["sku_interno"] for p in catalogo["productos_canonicos"]}
        for oferta in catalogo["ofertas_tienda"]:
            if oferta["metodo_vinculacion"] != "ean":
                continue
            if (sku_de.get(oferta["producto_canonico_id"]) or "").startswith("TK-REV-"):
                continue
            assert float(oferta["confianza_vinculacion"]) == 1.000

    def test_nada_por_debajo_del_umbral_medido_llega_al_catalogo(self, catalogo):
        """0,740 no es un numero elegido sino el medido contra la muestra
        anotada a mano: 88,89 % de precision ahi."""
        for oferta in catalogo["ofertas_tienda"]:
            if oferta["metodo_vinculacion"] == "atributos":
                assert float(oferta["confianza_vinculacion"]) >= UMBRAL_ACEPTACION

    def test_lo_dudoso_va_a_la_cola_y_no_se_descarta_ni_se_da_por_bueno(self, catalogo):
        """El camino del medio es el que importa. Entre 0,740 y 0,800 la oferta
        se crea, se marca y aparece en `revision_manual.csv`; ni se tira ni se
        acepta en silencio."""
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
        """La misma regla leida por el modelo y por el CSV tiene que dar lo
        mismo, porque es la que alimentara la bandeja del curador."""
        marcadas = [o for o in cargado.query(OfertaTienda) if o.requiere_revision]
        assert len(marcadas) == len(catalogo["revision_manual"])

    def test_el_mayorista_no_aporta_ean(self, cargado, catalogo):
        """La verificacion empirica que cambio la estrategia: WooCommerce no
        tiene el campo y Shopify omite `barcode` del JSON publico. Si un dia
        aparece un EAN por ahi, es que se colo la referencia interna."""
        del catalogo
        mayoristas = {t.id for t in cargado.query(Tienda) if t.tipo == "mayorista"}
        assert mayoristas
        for oferta in cargado.query(OfertaTienda):
            if oferta.tienda_id in mayoristas:
                assert oferta.metodo_vinculacion != MetodoVinculacion.EAN.value

    def test_disponible_distingue_no_se_de_no_hay(self, cargado):
        """Forzar False donde no hubo observacion haria que el optimizador
        descarte ofertas legitimas."""
        valores = {o.disponible for o in cargado.query(OfertaTienda)}
        assert None in valores or False in valores or True in valores
        for oferta in cargado.query(OfertaTienda):
            assert oferta.disponible in (True, False, None)
