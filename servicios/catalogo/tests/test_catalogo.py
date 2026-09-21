"""Invariantes del catalogo de tres capas.

Lo que se prueba aqui no son las columnas sino las decisiones: que un precio
pertenezca a la oferta y no al producto, que "no se" sea distinto de "no hay",
y que un renglon que nadie supo resolver no se pueda quedar callado.
"""

from __future__ import annotations

import uuid

import pytest
from conftest import (
    CURADOR,
    ahora,
    crear_concepto,
    crear_oferta,
    crear_producto,
    crear_tienda,
)
from sqlalchemy.exc import IntegrityError
from tukit_catalogo.modelos import (
    UMBRAL_REVISION_MANUAL,
    ItemListaOficial,
    ListaOficial,
    Nivel,
    PrecioOferta,
    ProductoCanonico,
    TareaImportacion,
    VersionListaOficial,
)


class TestTresCapas:
    def test_un_producto_puede_venderse_en_varias_tiendas_a_precios_distintos(self, sesion):
        """Esto era inexpresable en el esquema viejo, donde el precio era
        columna del producto. Comparar precio entre tiendas es el nucleo de
        la propuesta de valor, asi que la prueba vale por el diseno entero."""
        concepto = crear_concepto(sesion)
        producto = crear_producto(sesion, concepto)
        exito = crear_tienda(sesion, "exito")
        panamericana = crear_tienda(sesion, "panamericana")

        for tienda, centavos in ((exito, 480_000), (panamericana, 520_000)):
            oferta = crear_oferta(sesion, producto, tienda)
            sesion.add(
                PrecioOferta(
                    oferta_id=oferta.id,
                    valor_centavos=centavos,
                    fuente="scraper",
                    vigente_desde=ahora())
            )
        sesion.flush()

        precios = sorted(p.valor_centavos for p in sesion.query(PrecioOferta))
        assert precios == [480_000, 520_000]

    def test_una_tienda_no_puede_ofrecer_dos_veces_el_mismo_producto(self, sesion):
        concepto = crear_concepto(sesion)
        producto = crear_producto(sesion, concepto)
        tienda = crear_tienda(sesion)
        crear_oferta(sesion, producto, tienda)

        with pytest.raises(IntegrityError):
            crear_oferta(sesion, producto, tienda)
            sesion.flush()

    def test_solo_puede_haber_un_precio_vigente_por_oferta(self, sesion):
        """Sin esto, "el precio de hoy" es una consulta ambigua, que es
        justo lo que les pasaba a las dos tablas de precio anteriores."""
        concepto = crear_concepto(sesion)
        oferta = crear_oferta(
            sesion, crear_producto(sesion, concepto), crear_tienda(sesion)
        )
        for _ in range(2):
            sesion.add(
                PrecioOferta(
                    oferta_id=oferta.id,
                    valor_centavos=400_000,
                    fuente="scraper",
                    vigente_desde=ahora())
            )

        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_un_precio_cerrado_no_bloquea_al_siguiente(self, sesion):
        concepto = crear_concepto(sesion)
        oferta = crear_oferta(
            sesion, crear_producto(sesion, concepto), crear_tienda(sesion)
        )
        viejo = PrecioOferta(
            oferta_id=oferta.id,
            valor_centavos=400_000,
            fuente="scraper",
            vigente_desde=ahora())
        sesion.add(viejo)
        sesion.flush()

        viejo.vigente_hasta = ahora()
        sesion.add(
            PrecioOferta(
                oferta_id=oferta.id,
                valor_centavos=450_000,
                fuente="scraper",
                vigente_desde=ahora())
        )
        sesion.flush()

        vigentes = [p for p in sesion.query(PrecioOferta) if p.vigente]
        assert len(vigentes) == 1
        assert vigentes[0].valor_centavos == 450_000

    def test_no_se_puede_borrar_un_concepto_que_tiene_productos(self, sesion):
        """RESTRICT y no CASCADE: borrar el concepto `cuaderno` no puede
        llevarse por delante los cuadernos del catalogo."""
        concepto = crear_concepto(sesion)
        crear_producto(sesion, concepto)
        sesion.delete(concepto)

        with pytest.raises(IntegrityError):
            sesion.flush()


class TestDisponibilidadDeTresValores:
    def test_desconocido_no_es_lo_mismo_que_agotado(self, sesion):
        """El mayorista no reporta stock. Forzar False haria que el
        optimizador descarte ofertas legitimas por una observacion que nunca
        se hizo."""
        concepto = crear_concepto(sesion)
        producto = crear_producto(sesion, concepto)

        desconocida = crear_oferta(sesion, producto, crear_tienda(sesion, "mayorista"))
        agotada = crear_oferta(
            sesion, producto, crear_tienda(sesion, "exito"), disponible=False
        )

        assert desconocida.disponible is None
        assert agotada.disponible is False
        assert desconocida.disponible is not agotada.disponible


class TestVinculacionPorAtributos:
    def test_la_vinculacion_floja_por_atributos_cae_en_revision(self, sesion):
        """Vincular por atributos no es un caso degradado sino el camino
        normal del canal mayorista, donde el EAN valido es del 0,00 %."""
        concepto = crear_concepto(sesion)
        producto = crear_producto(sesion, concepto)

        floja = crear_oferta(
            sesion, producto, crear_tienda(sesion, "mayorista"), "atributos", 0.640
        )
        assert floja.requiere_revision

    def test_la_vinculacion_por_ean_no_cae_en_revision_aunque_baje_la_confianza(
        self, sesion
    ):
        """Solo el metodo por atributos entra a la cola. Un EAN coincide o no
        coincide; no tiene grados."""
        concepto = crear_concepto(sesion)
        oferta = crear_oferta(
            sesion, crear_producto(sesion, concepto), crear_tienda(sesion), "ean", 0.500
        )
        assert not oferta.requiere_revision

    def test_por_encima_del_umbral_la_vinculacion_se_da_por_buena(self, sesion):
        concepto = crear_concepto(sesion)
        oferta = crear_oferta(
            sesion,
            crear_producto(sesion, concepto),
            crear_tienda(sesion, "mayorista"),
            "atributos",
            UMBRAL_REVISION_MANUAL + 0.05)
        assert not oferta.requiere_revision

    def test_la_confianza_no_puede_salirse_del_rango(self, sesion):
        concepto = crear_concepto(sesion)
        with pytest.raises(IntegrityError):
            crear_oferta(
                sesion, crear_producto(sesion, concepto), crear_tienda(sesion), "ean", 1.5
            )
            sesion.flush()


class TestNiveles:
    def test_los_tres_niveles_conviven_bajo_un_concepto(self, sesion):
        """Es lo que hace posible el kit multiperfil: el mismo concepto
        resuelto a tres precios distintos."""
        concepto = crear_concepto(sesion)
        for nivel in Nivel:
            crear_producto(sesion, concepto, nivel)
        sesion.flush()

        niveles = {p.nivel for p in sesion.query(ProductoCanonico)}
        assert niveles == {"economico", "confiable", "premium"}

    def test_un_nivel_inventado_se_rechaza(self, sesion):
        """`personalizado` NO es un nivel: el personaje es columna aparte,
        porque un producto con personaje tambien tiene nivel de marca."""
        concepto = crear_concepto(sesion)
        sesion.add(
            ProductoCanonico(
                concepto_id=concepto.id,
                sku_interno="TK-MALO",
                nombre="x",
                nivel="personalizado",
                curado_por=CURADOR)
        )
        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_un_personaje_convive_con_su_nivel_de_marca(self, sesion):
        concepto = crear_concepto(sesion, "cuaderno_personaje", admite_personaje=True)
        p = crear_producto(sesion, concepto, Nivel.PREMIUM, personaje="spiderman")
        assert (p.personaje, p.nivel) == ("spiderman", "premium")


class TestListasOficiales:
    def _version(self, sesion) -> VersionListaOficial:
        lista = ListaOficial(colegio_id=uuid.uuid4(), grado="3", anio_lectivo=2026)
        sesion.add(lista)
        sesion.flush()
        v = VersionListaOficial(lista_id=lista.id, numero=1)
        sesion.add(v)
        sesion.flush()
        return v

    def test_un_renglon_sin_concepto_debe_ir_a_revision(self, sesion):
        """Un renglon que nadie supo resolver no puede quedarse callado y
        salir del kit sin que nadie se entere."""
        version = self._version(sesion)
        sesion.add(
            ItemListaOficial(
                version_id=version.id,
                orden=1,
                texto_original="cartuchera con cierre",
                concepto_id=None,
                requiere_revision=False)
        )
        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_un_renglon_sin_concepto_marcado_para_revision_si_se_acepta(self, sesion):
        version = self._version(sesion)
        sesion.add(
            ItemListaOficial(
                version_id=version.id,
                orden=1,
                texto_original="cartuchera con cierre",
                concepto_id=None,
                requiere_revision=True)
        )
        sesion.flush()
        assert sesion.query(ItemListaOficial).count() == 1

    def test_solo_una_version_vigente_por_lista(self, sesion):
        version = self._version(sesion)
        sesion.add(VersionListaOficial(lista_id=version.lista_id, numero=2))
        with pytest.raises(IntegrityError):
            sesion.flush()


class TestTareaImportacion:
    def test_una_tarea_fallida_sin_diagnostico_se_rechaza(self, sesion):
        """Una tarea fallida que nadie puede atender es ruido, no un aviso."""
        sesion.add(TareaImportacion(origen="pdf", estado="fallida"))
        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_una_tarea_fallida_con_caso_abierto_se_acepta(self, sesion):
        sesion.add(TareaImportacion(origen="pdf", estado="fallida", caso_id=uuid.uuid4()))
        sesion.flush()
        assert sesion.query(TareaImportacion).count() == 1

    def test_la_etapa_completada_es_el_punto_de_reanudacion(self, sesion):
        """Reanudar desde la ultima etapa buena evita repagar la percepcion,
        que es la etapa cara."""
        t = TareaImportacion(
            origen="pdf",
            estado="fallida",
            etapa_completada="percepcion",
            etapa_actual="normalizacion",
            error="tiempo de espera agotado")
        sesion.add(t)
        sesion.flush()
        assert t.etapa_completada == "percepcion"
