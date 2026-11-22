from __future__ import annotations

import math
import uuid
from datetime import timedelta

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
    CALIDAD_POR_NIVEL,
    UMBRAL_REVISION_MANUAL,
    Concepto,
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
        concepto = crear_concepto(sesion)
        producto = crear_producto(sesion, concepto)
        exito = crear_tienda(sesion, "exito")
        panamericana = crear_tienda(sesion, "panamericana")

        for tienda, centavos in ((exito, 480_000), (panamericana, 520_000)):
            oferta = crear_oferta(sesion, producto, tienda)
            sesion.add(
                PrecioOferta(
                    oferta_id=oferta.id, valor_centavos=centavos, fuente="scraper", vigente_desde=ahora()
                )
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
        concepto = crear_concepto(sesion)
        oferta = crear_oferta(sesion, crear_producto(sesion, concepto), crear_tienda(sesion))
        for _ in range(2):
            sesion.add(
                PrecioOferta(
                    oferta_id=oferta.id, valor_centavos=400_000, fuente="scraper", vigente_desde=ahora()
                )
            )

        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_un_precio_cerrado_no_bloquea_al_siguiente(self, sesion):
        concepto = crear_concepto(sesion)
        oferta = crear_oferta(sesion, crear_producto(sesion, concepto), crear_tienda(sesion))
        # En Windows dos `ahora()` seguidos pueden coincidir.
        viejo = PrecioOferta(
            oferta_id=oferta.id,
            valor_centavos=400_000,
            fuente="scraper",
            vigente_desde=ahora() - timedelta(seconds=1),
        )
        sesion.add(viejo)
        sesion.flush()

        viejo.vigente_hasta = ahora()
        sesion.add(
            PrecioOferta(oferta_id=oferta.id, valor_centavos=450_000, fuente="scraper", vigente_desde=ahora())
        )
        sesion.flush()

        vigentes = [p for p in sesion.query(PrecioOferta) if p.vigente]
        assert len(vigentes) == 1
        assert vigentes[0].valor_centavos == 450_000

    def test_no_se_puede_borrar_un_concepto_que_tiene_productos(self, sesion):
        concepto = crear_concepto(sesion)
        crear_producto(sesion, concepto)
        sesion.delete(concepto)

        with pytest.raises(IntegrityError):
            sesion.flush()


class TestDisponibilidadDeTresValores:
    def test_desconocido_no_es_lo_mismo_que_agotado(self, sesion):
        concepto = crear_concepto(sesion)
        producto = crear_producto(sesion, concepto)

        desconocida = crear_oferta(sesion, producto, crear_tienda(sesion, "mayorista"))
        agotada = crear_oferta(sesion, producto, crear_tienda(sesion, "exito"), disponible=False)

        assert desconocida.disponible is None
        assert agotada.disponible is False
        assert desconocida.disponible is not agotada.disponible


class TestVinculacionPorAtributos:
    def test_la_vinculacion_floja_por_atributos_cae_en_revision(self, sesion):
        concepto = crear_concepto(sesion)
        producto = crear_producto(sesion, concepto)

        floja = crear_oferta(sesion, producto, crear_tienda(sesion, "mayorista"), "atributos", 0.640)
        assert floja.requiere_revision

    def test_la_vinculacion_por_ean_no_cae_en_revision_aunque_baje_la_confianza(self, sesion):
        concepto = crear_concepto(sesion)
        oferta = crear_oferta(sesion, crear_producto(sesion, concepto), crear_tienda(sesion), "ean", 0.500)
        assert not oferta.requiere_revision

    def test_por_encima_del_umbral_la_vinculacion_se_da_por_buena(self, sesion):
        concepto = crear_concepto(sesion)
        oferta = crear_oferta(
            sesion,
            crear_producto(sesion, concepto),
            crear_tienda(sesion, "mayorista"),
            "atributos",
            UMBRAL_REVISION_MANUAL + 0.05,
        )
        assert not oferta.requiere_revision

    def test_la_confianza_no_puede_salirse_del_rango(self, sesion):
        concepto = crear_concepto(sesion)
        with pytest.raises(IntegrityError):
            crear_oferta(sesion, crear_producto(sesion, concepto), crear_tienda(sesion), "ean", 1.5)
            sesion.flush()


class TestNiveles:
    def test_los_tres_niveles_conviven_bajo_un_concepto(self, sesion):
        concepto = crear_concepto(sesion)
        for nivel in Nivel:
            crear_producto(sesion, concepto, nivel)
        sesion.flush()

        niveles = {p.nivel for p in sesion.query(ProductoCanonico)}
        assert niveles == {"economico", "confiable", "premium"}

    def test_un_nivel_inventado_se_rechaza(self, sesion):
        concepto = crear_concepto(sesion)
        sesion.add(
            ProductoCanonico(
                concepto_id=concepto.id,
                sku_interno="TK-MALO",
                nombre="x",
                nivel="personalizado",
                curado_por=CURADOR,
            )
        )
        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_un_personaje_convive_con_su_nivel_de_marca(self, sesion):
        concepto = crear_concepto(sesion, "cuaderno_personaje", admite_personaje=True)
        p = crear_producto(sesion, concepto, Nivel.PREMIUM, personaje="spiderman")
        assert (p.personaje, p.nivel) == ("spiderman", "premium")


class TestEjesOrtogonales:
    def test_un_producto_premium_tambien_puede_ser_de_spiderman(self, sesion):
        concepto = crear_concepto(sesion, "cuaderno", admite_personaje=True)
        cuaderno = crear_producto(sesion, concepto, Nivel.PREMIUM, personaje="spiderman")
        sesion.flush()

        assert cuaderno.nivel == "premium"
        assert cuaderno.personaje == "spiderman"
        assert CALIDAD_POR_NIVEL[Nivel(cuaderno.nivel)] == max(CALIDAD_POR_NIVEL.values())

    def test_licencia_no_es_un_nivel(self, sesion):
        concepto = crear_concepto(sesion, "cuaderno", admite_personaje=True)
        sesion.add(
            ProductoCanonico(
                concepto_id=concepto.id,
                sku_interno="TK-LIC",
                nombre="Cuaderno Spiderman",
                nivel="licencia",
                personaje="spiderman",
                curado_por=CURADOR,
            )
        )
        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_el_mismo_personaje_vive_en_los_tres_niveles(self, sesion):
        concepto = crear_concepto(sesion, "cuaderno", admite_personaje=True)
        for nivel in Nivel:
            crear_producto(sesion, concepto, nivel, personaje="spiderman")
        sesion.flush()

        con_personaje = sesion.query(ProductoCanonico).filter_by(personaje="spiderman")
        assert {p.nivel for p in con_personaje} == {"economico", "confiable", "premium"}


class TestUnidadDeCompra:
    def test_por_omision_un_producto_se_vende_de_a_una_unidad(self, sesion):
        producto = crear_producto(sesion, crear_concepto(sesion))
        assert (producto.unidad_base, producto.unidades_por_empaque) == ("unidad", 1)

    def test_la_caja_de_doce_lapices_no_son_doce_cajas(self, sesion):
        caja = crear_producto(sesion, crear_concepto(sesion, "lapiz"), unidades_por_empaque=12)
        assert math.ceil(12 / caja.unidades_por_empaque) == 1
        assert math.ceil(13 / caja.unidades_por_empaque) == 2

    def test_el_empaque_deja_de_confundirse_con_la_dimension(self, sesion):
        bloc = crear_producto(
            sesion,
            crear_concepto(sesion, "bloc_origami"),
            unidad_base="hoja",
            unidades_por_empaque=50,
            atributos={"lado_cm": 15},
        )
        assert (bloc.unidad_base, bloc.unidades_por_empaque) == ("hoja", 50)
        assert bloc.atributos == {"lado_cm": 15}

    def test_un_empaque_vacio_se_rechaza(self, sesion):
        with pytest.raises(IntegrityError):
            crear_producto(sesion, crear_concepto(sesion), unidades_por_empaque=0)
            sesion.flush()

    def test_una_unidad_base_inventada_se_rechaza(self, sesion):
        with pytest.raises(IntegrityError):
            crear_producto(sesion, crear_concepto(sesion), unidad_base="x")
            sesion.flush()


class TestTipoItem:
    def test_por_omision_un_concepto_es_papeleria_comprable(self, sesion):
        assert crear_concepto(sesion).tipo_item == "util"

    def test_los_renglones_que_no_se_compran_tienen_donde_decirlo(self, sesion):
        casos = {
            "raz_plus": "licencia_digital",
            "diccionario_de_casa": "no_comprar",
            "textos_del_anio": "diferido",
            "camibuso": "uniforme",
        }
        for codigo, tipo in casos.items():
            crear_concepto(sesion, codigo, tipo_item=tipo)
        sesion.flush()

        assert {c.tipo_item for c in sesion.query(Concepto)} == set(casos.values())

    def test_un_tipo_inventado_se_rechaza(self, sesion):
        with pytest.raises(IntegrityError):
            crear_concepto(sesion, "raro", tipo_item="quiza")
            sesion.flush()

    def test_la_metrica_de_catalogo_sin_huecos_solo_mira_los_utiles(self, sesion):
        cuaderno = crear_concepto(sesion, "cuaderno")
        crear_concepto(sesion, "raz_plus", tipo_item="licencia_digital")
        crear_producto(sesion, cuaderno)
        sesion.flush()

        con_producto = {p.concepto_id for p in sesion.query(ProductoCanonico)}
        huecos = [
            c for c in sesion.query(Concepto).filter(Concepto.tipo_item == "util") if c.id not in con_producto
        ]
        assert huecos == []


class TestElEsquemaSePuedeMigrar:
    def test_ninguna_tabla_queda_fuera_del_orden_de_creacion(self):
        import warnings

        from sqlalchemy.exc import SAWarning
        from tukit_catalogo.modelos import Base

        with warnings.catch_warnings():
            warnings.simplefilter("error", SAWarning)
            ordenadas = Base.metadata.sorted_tables

        assert len(ordenadas) == len(Base.metadata.tables)

    def test_ninguna_restriccion_unica_repite_la_llave_primaria(self):
        from sqlalchemy import UniqueConstraint
        from tukit_catalogo.modelos import Base

        repetidas = []
        for tabla in Base.metadata.tables.values():
            columnas_pk = {c.name for c in tabla.primary_key.columns}
            for r in tabla.constraints:
                if isinstance(r, UniqueConstraint) and {c.name for c in r.columns} == columnas_pk:
                    repetidas.append(f"  {tabla.name}.{r.name} repite la llave primaria")

        assert not repetidas, "Restricciones unicas redundantes:\n" + "\n".join(repetidas)

    def test_cada_tabla_va_despues_de_aquellas_a_las_que_apunta(self):
        from tukit_catalogo.modelos import Base

        posicion = {t.name: i for i, t in enumerate(Base.metadata.sorted_tables)}
        problemas = []
        for tabla in Base.metadata.sorted_tables:
            for fk in tabla.foreign_keys:
                destino = fk.column.table.name
                if destino == tabla.name or fk.constraint.use_alter:
                    continue
                if posicion[destino] > posicion[tabla.name]:
                    problemas.append(f"  {tabla.name} se crea antes que {destino}, al que apunta")

        assert not problemas, "El orden de creacion es imposible:\n" + "\n".join(problemas)


class TestTipoItemPorRenglon:
    def _version(self, sesion) -> VersionListaOficial:
        lista = ListaOficial(colegio_id=uuid.uuid4(), grado="3", anio_lectivo=2026)
        sesion.add(lista)
        sesion.flush()
        v = VersionListaOficial(lista_id=lista.id, numero=1)
        sesion.add(v)
        sesion.flush()
        return v

    def _item(self, sesion, concepto, **kw) -> ItemListaOficial:
        item = ItemListaOficial(
            version_id=self._version(sesion).id,
            orden=kw.pop("orden", 1),
            texto_original=kw.pop("texto", "1 diccionario escolar"),
            concepto_id=concepto.id,
            **kw,
        )
        sesion.add(item)
        sesion.flush()
        return item

    def test_un_renglon_sin_tipo_propio_hereda_el_del_concepto(self, sesion):
        concepto = crear_concepto(sesion, "diccionario")
        item = self._item(sesion, concepto)

        assert item.tipo_item is None
        assert item.tipo_efectivo(concepto) == "util"

    def test_el_renglon_le_gana_al_concepto(self, sesion):
        concepto = crear_concepto(sesion, "diccionario")
        item = self._item(
            sesion, concepto, texto="Diccionario: el disponible en casa", tipo_item="no_comprar"
        )

        assert concepto.tipo_item == "util"
        assert item.tipo_efectivo(concepto) == "no_comprar"

    def test_dos_colegios_pueden_discrepar_sobre_el_mismo_concepto(self, sesion):
        concepto = crear_concepto(sesion, "diccionario")
        en_casa = self._item(sesion, concepto, tipo_item="no_comprar")
        se_compra = self._item(sesion, concepto)

        assert {en_casa.tipo_efectivo(concepto), se_compra.tipo_efectivo(concepto)} == {
            "no_comprar",
            "util",
        }

    def test_un_tipo_inventado_en_el_renglon_se_rechaza(self, sesion):
        concepto = crear_concepto(sesion, "diccionario")
        with pytest.raises(IntegrityError):
            self._item(sesion, concepto, tipo_item="quiza")

    def test_un_renglon_sabe_si_tukit_puede_venderlo(self, sesion):
        concepto = crear_concepto(sesion, "texto_lenguaje", tipo_item="texto")
        exclusiva = self._item(
            sesion,
            concepto,
            texto="Sistema Flex TAC-Lenguaje 1",
            modo_adquisicion="edicion_exclusiva",
            instruccion_colegio="Edicion exclusiva para la institucion. Se adquiere con la editorial.",
        )
        libre = self._item(
            sesion,
            concepto,
            texto="La casa de los espiritus. Isabella Allende. Cualquier editorial",
            modo_adquisicion="libro_libre",
        )

        assert not exclusiva.surtible
        assert libre.surtible

    def test_por_omision_no_se_asume_que_el_colegio_cerro_el_item(self, sesion):
        concepto = crear_concepto(sesion, "cuaderno")
        assert self._item(sesion, concepto).modo_adquisicion == "mercado_abierto"

    def test_un_modo_de_adquisicion_inventado_se_rechaza(self, sesion):
        concepto = crear_concepto(sesion, "cuaderno")
        with pytest.raises(IntegrityError):
            self._item(sesion, concepto, modo_adquisicion="por_ahi")

    def test_lo_que_no_se_puede_surtir_debe_decir_como_conseguirlo(self, sesion):
        concepto = crear_concepto(sesion, "texto_lenguaje", tipo_item="texto")
        with pytest.raises(IntegrityError):
            self._item(sesion, concepto, modo_adquisicion="edicion_exclusiva")

    def test_una_linea_informativa_con_instruccion_si_se_acepta(self, sesion):
        concepto = crear_concepto(sesion, "texto_lenguaje", tipo_item="texto")
        item = self._item(
            sesion,
            concepto,
            modo_adquisicion="venta_directa_editorial",
            instruccion_colegio=("Las editoriales venden directamente a las familias el sabado 24 de enero."),
        )

        assert not item.surtible
        assert item.instruccion_colegio

    def test_una_licencia_digital_guarda_su_enlace_de_pago(self, sesion):
        concepto = crear_concepto(sesion, "raz_plus", tipo_item="licencia_digital")
        item = self._item(
            sesion,
            concepto,
            texto="Plan lector virtual RAZ-PLUS",
            modo_adquisicion="plataforma",
            instruccion_colegio="Se adquiere en linea.",
            url_externa="https://pagoslearning.com/",
        )

        assert item.url_externa == "https://pagoslearning.com/"


class TestVocabularioDeUnidad:
    def _item(self, sesion, **kw) -> ItemListaOficial:
        lista = ListaOficial(colegio_id=uuid.uuid4(), grado="3", anio_lectivo=2026)
        sesion.add(lista)
        sesion.flush()
        version = VersionListaOficial(lista_id=lista.id, numero=1)
        sesion.add(version)
        sesion.flush()
        item = ItemListaOficial(
            version_id=version.id,
            orden=1,
            texto_original="12 lapices",
            concepto_id=crear_concepto(sesion, f"c{uuid.uuid4().hex[:6]}").id,
            **kw,
        )
        sesion.add(item)
        sesion.flush()
        return item

    def test_el_renglon_admite_el_mismo_vocabulario_que_el_producto(self, sesion):
        for unidad in ("unidad", "hoja", "pliego", "metro", "gramo", "mililitro"):
            assert self._item(sesion, unidad=unidad).unidad == unidad

    def test_una_unidad_fuera_del_vocabulario_se_rechaza(self, sesion):
        with pytest.raises(IntegrityError):
            self._item(sesion, unidad="resma")

    def test_la_unidad_puede_faltar_y_entonces_se_cuenta_por_unidad(self, sesion):
        assert self._item(sesion).unidad is None

    def test_la_division_de_empaque_es_expresable_de_punta_a_punta(self, sesion):
        concepto = crear_concepto(sesion, "lapiz")
        caja = crear_producto(sesion, concepto, unidad_base="unidad", unidades_por_empaque=12)
        item = self._item(sesion, cantidad=12, unidad="unidad")

        assert item.unidad == caja.unidad_base
        assert -(-item.cantidad // caja.unidades_por_empaque) == 1


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
        version = self._version(sesion)
        sesion.add(
            ItemListaOficial(
                version_id=version.id,
                orden=1,
                texto_original="cartuchera con cierre",
                concepto_id=None,
                requiere_revision=False,
            )
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
                requiere_revision=True,
            )
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
        sesion.add(TareaImportacion(origen="pdf", estado="fallida"))
        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_una_tarea_fallida_con_mensaje_se_acepta(self, sesion):
        sesion.add(TareaImportacion(origen="pdf", estado="fallida", error="PDF ilegible"))
        sesion.flush()
        assert sesion.query(TareaImportacion).count() == 1

    def test_la_tarea_no_guarda_el_caso_que_la_atiende(self, sesion):
        assert not hasattr(TareaImportacion, "caso_id")

    def test_la_etapa_completada_es_el_punto_de_reanudacion(self, sesion):
        t = TareaImportacion(
            origen="pdf",
            estado="fallida",
            etapa_completada="percepcion",
            etapa_actual="normalizacion",
            error="tiempo de espera agotado",
        )
        sesion.add(t)
        sesion.flush()
        assert t.etapa_completada == "percepcion"
