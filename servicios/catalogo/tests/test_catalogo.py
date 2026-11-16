"""Invariantes del catalogo de tres capas.

Lo que se prueba aqui no son las columnas sino las decisiones: que un precio
pertenezca a la oferta y no al producto, que "no se" sea distinto de "no hay",
y que un renglon que nadie supo resolver no se pueda quedar callado.
"""

from __future__ import annotations

import math
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
        """Sin esto, "el precio de hoy" es una consulta ambigua, que es
        justo lo que les pasaba a las dos tablas de precio anteriores."""
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
        viejo = PrecioOferta(
            oferta_id=oferta.id, valor_centavos=400_000, fuente="scraper", vigente_desde=ahora()
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
        agotada = crear_oferta(sesion, producto, crear_tienda(sesion, "exito"), disponible=False)

        assert desconocida.disponible is None
        assert agotada.disponible is False
        assert desconocida.disponible is not agotada.disponible


class TestVinculacionPorAtributos:
    def test_la_vinculacion_floja_por_atributos_cae_en_revision(self, sesion):
        """Vincular por atributos no es un caso degradado sino el camino
        normal del canal mayorista, donde el EAN valido es del 0,00 %."""
        concepto = crear_concepto(sesion)
        producto = crear_producto(sesion, concepto)

        floja = crear_oferta(sesion, producto, crear_tienda(sesion, "mayorista"), "atributos", 0.640)
        assert floja.requiere_revision

    def test_la_vinculacion_por_ean_no_cae_en_revision_aunque_baje_la_confianza(self, sesion):
        """Solo el metodo por atributos entra a la cola. Un EAN coincide o no
        coincide; no tiene grados."""
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
    """`nivel` y `personaje` miden cosas distintas y no se colapsan.

    Esta clase existe por un defecto concreto y medible, no por prolijidad.
    En `Arquitectura/datos_fuente/tier_marcas.json` el tier `licencia` esta
    listado al lado de `economica`, `confiable` y `premium` como si fuera uno
    mas, y `utilidad_por_tier['licencia']` vale `null`. Las 17 marcas que caen
    ahi son Spiderman, Frozen, Minecraft, Disney y similares.

    La consecuencia es que un cuaderno de Spiderman quedaba clasificado como
    `licencia`, perdia su nivel de calidad de marca y el optimizador se
    quedaba sin puntaje con que compararlo. Por eso hoy es imposible ofrecer
    un kit con premium, economico y varios personalizados a la vez: el eje que
    permite ordenar por calidad desaparece justo en los productos con
    personaje.

    El esquema ya tenia las dos columnas separadas. Lo que faltaba era fijarlo
    con una prueba, porque volver a colapsarlas no rompe nada visible: no
    lanza error, solo deja al optimizador sin con que puntuar.
    """

    def test_un_producto_premium_tambien_puede_ser_de_spiderman(self, sesion):
        """Los dos ejes a la vez en la misma fila, que es lo que el tier
        `licencia` hacia inexpresable."""
        concepto = crear_concepto(sesion, "cuaderno", admite_personaje=True)
        cuaderno = crear_producto(sesion, concepto, Nivel.PREMIUM, personaje="spiderman")
        sesion.flush()

        assert cuaderno.nivel == "premium"
        assert cuaderno.personaje == "spiderman"
        # Y conserva puntaje de calidad, que es justo lo que se perdia cuando
        # el personaje se comia el nivel.
        assert CALIDAD_POR_NIVEL[Nivel(cuaderno.nivel)] == max(CALIDAD_POR_NIVEL.values())

    def test_licencia_no_es_un_nivel(self, sesion):
        """El valor exacto que traia el fichero de tiers. Si algun dia entra,
        entra con `utilidad` nula y el producto deja de ser puntuable."""
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
        """La oferta que el colapso hacia imposible: el nino quiere Spiderman
        y el papa decide cuanto pagar por el, que son dos decisiones."""
        concepto = crear_concepto(sesion, "cuaderno", admite_personaje=True)
        for nivel in Nivel:
            crear_producto(sesion, concepto, nivel, personaje="spiderman")
        sesion.flush()

        con_personaje = sesion.query(ProductoCanonico).filter_by(personaje="spiderman")
        assert {p.nivel for p in con_personaje} == {"economico", "confiable", "premium"}


class TestUnidadDeCompra:
    """Que el tamano del empaque sea un dato y no una adivinanza sobre el nombre.

    El defecto concreto: para "Bloc origami x 50 unidades (15 x 15 cm)" el
    campo `atributos['cantidades_declaradas']` vale
    `['15:cm', '15:x', '50:unidades', '50:x']`. El 50 es el tamano del empaque
    y el 15 es una dimension fisica, y nada en el dato los distingue. De ahi
    sale el error de carrito: cuando la lista pide 12 lapices y el producto es
    una caja de 12, se suman 12 cajas en vez de una.
    """

    def test_por_omision_un_producto_se_vende_de_a_una_unidad(self, sesion):
        """El valor por omision tiene que ser el caso comun, porque la mayor
        parte de la papeleria se vende suelta y solo lo excepcional se anota."""
        producto = crear_producto(sesion, crear_concepto(sesion))
        assert (producto.unidad_base, producto.unidades_por_empaque) == ("unidad", 1)

    def test_la_caja_de_doce_lapices_no_son_doce_cajas(self, sesion):
        """La regla que estas dos columnas habilitan es
        `unidades_a_comprar = techo(cantidad_pedida / unidades_por_empaque)`.
        No se implementa aqui, que vive en el pipeline. Lo que se prueba es
        que el esquema la deja EXPRESAR, porque antes no la dejaba."""
        caja = crear_producto(sesion, crear_concepto(sesion, "lapiz"), unidades_por_empaque=12)
        assert math.ceil(12 / caja.unidades_por_empaque) == 1
        # Y lo que sobra se paga: 13 lapices son dos cajas, no una y cuarto.
        assert math.ceil(13 / caja.unidades_por_empaque) == 2

    def test_el_empaque_deja_de_confundirse_con_la_dimension(self, sesion):
        """El bloc de origami. El 50 sube a una columna con nombre y el 15 se
        queda en `atributos`, donde ya no puede leerse como una cantidad a
        comprar."""
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
        """Un empaque de cero unidades es una division por cero esperando su
        turno en la regla de compra."""
        with pytest.raises(IntegrityError):
            crear_producto(sesion, crear_concepto(sesion), unidades_por_empaque=0)
            sesion.flush()

    def test_una_unidad_base_inventada_se_rechaza(self, sesion):
        """`x` es exactamente lo que el parseo de "15 x 15" producia y llegaba
        a colarse como si fuera una unidad de medida."""
        with pytest.raises(IntegrityError):
            crear_producto(sesion, crear_concepto(sesion), unidad_base="x")
            sesion.flush()


class TestTipoItem:
    """No todo renglon de una lista escolar es algo que se compra.

    Forzarle un emparejamiento a "Diccionario: el disponible en casa" no es
    cobertura sino un defecto: el sistema le vende al acudiente algo que el
    colegio dijo explicitamente que no hay que comprar.
    """

    def test_por_omision_un_concepto_es_papeleria_comprable(self, sesion):
        assert crear_concepto(sesion).tipo_item == "util"

    def test_los_renglones_que_no_se_compran_tienen_donde_decirlo(self, sesion):
        """Los cuatro casos salen de listas reales del corpus, no de un
        catalogo de posibilidades imaginadas."""
        casos = {
            # "Plan lector virtual RAZ-PLUS ... Link de pago: https://pagoslearning.com/"
            "raz_plus": "licencia_digital",
            "diccionario_de_casa": "no_comprar",
            # "durante el ano se incluiran algunos textos"
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
        """Un concepto `licencia_digital` sin producto no es un hueco del
        catalogo: es un item que por diseno no se compra aqui. Contarlo
        inflaria el hueco y empujaria a taparlo con un producto inventado."""
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
    """Las tablas tienen que poder crearse en ALGUN orden valido.

    `create_all` esconde este problema: cuando dos tablas se apuntan entre si,
    SQLAlchemy lo resuelve solo, creando las tablas primero y las llaves
    despues con un ALTER. Alembic no hace eso. Emite `CREATE TABLE` en el
    orden que pueda y la migracion **revienta al aplicarse**, con un mensaje
    que habla de una tabla que "no existe" aunque este declarada dos lineas
    mas abajo.

    O sea que la suite entera puede estar verde contra SQLite y aun asi no
    haber forma de llevar el esquema a una base real. Por eso esta prueba
    mira el grafo de dependencias y no el resultado de crear las tablas.

    El caso concreto: `grupo_variante.representante_id` apunta a
    `producto_canonico` y `producto_canonico.grupo_variante_id` apunta de
    vuelta a `grupo_variante`. El ciclo es legitimo en el dominio —un grupo
    conoce a su representante y un producto sabe a que grupo pertenece— asi
    que no se rompe la relacion: se marca una de las dos llaves con
    `use_alter`, que es la forma de decir "esta se crea despues".

    Ojo con la funcion de aptitud `test_el_grafo_de_dependencias_entre_servicios_es_aciclico`:
    solo mira ciclos ENTRE servicios y descarta a proposito los que quedan
    dentro de uno. Este vive dentro de Catalogo, asi que le pasa por debajo, y
    de ahi que haga falta esta prueba aparte.
    """

    def test_ninguna_tabla_queda_fuera_del_orden_de_creacion(self):
        import warnings

        from sqlalchemy.exc import SAWarning
        from tukit_catalogo.modelos import Base

        with warnings.catch_warnings():
            warnings.simplefilter("error", SAWarning)
            ordenadas = Base.metadata.sorted_tables

        assert len(ordenadas) == len(Base.metadata.tables)

    def test_ninguna_restriccion_unica_repite_la_llave_primaria(self):
        """Una restriccion unica sobre las mismas columnas que la llave
        primaria no agrega ninguna garantia: la primaria ya la da.

        No es solo ruido. Postgres las funde al crear la tabla y la que
        sobrevive se queda con el nombre de la otra, asi que el esquema real
        deja de parecerse al declarado y la comparacion contra los modelos
        reporta una diferencia eterna que nadie sabe como cerrar. Ademas paga
        un indice de mas en cada escritura.
        """
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
        """Lo que de verdad importa no es que el orden exista sino que sea
        correcto: toda tabla referenciada tiene que venir antes, salvo las
        llaves marcadas para crearse aparte."""
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
    """El tipo se decide por RENGLON, no solo por concepto.

    El concepto es la necesidad abstracta que comparten los 17 colegios, y ahi
    `diccionario = util` es correcto. Pero "Diccionario: el disponible en casa"
    no es una propiedad del concepto *diccionario*: es una propiedad de ESE
    renglon de ESA lista. Otro colegio del mismo corpus si pide comprarlo.

    Si el tipo viviera solo en el concepto, marcar `diccionario` como
    `no_comprar` por un colegio lo volveria no comprable para los diecisiete.
    El concepto queda como valor por omision heredable y el renglon manda.
    """

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
        """Nulo NO significa `util`: significa "lo que diga el concepto". La
        diferencia importa porque permite cambiar el concepto y que los
        renglones que no opinaron sigan al dia."""
        concepto = crear_concepto(sesion, "diccionario")
        item = self._item(sesion, concepto)

        assert item.tipo_item is None
        assert item.tipo_efectivo(concepto) == "util"

    def test_el_renglon_le_gana_al_concepto(self, sesion):
        """El caso que motiva la columna entera: mismo concepto comprable, un
        colegio que dice que no lo compren."""
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
        """Hay textos que el colegio cerro, y no por falta de proveedor. De los
        14 PDF del corpus: "edicion exclusiva para la institucion" (Flex TAC),
        "venta directa a las familias... las editoriales reciben dinero en
        efectivo" (Osito de Miel). Tukit no puede surtir ninguno de los dos, y
        el kit tiene que poder decirlo en vez de prometerlo."""
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
        """Una linea informativa sin instruccion no informa nada.

        Decirle al acudiente "esto no te lo vendemos" y callar donde se
        consigue lo deja peor que antes: el dolor que la encuesta mide es
        recorrer papelerias y perder tiempo, y un hueco sin explicacion
        reproduce ese dolor con el agravante de que lo descubre tarde.
        """
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
        """El contrato promete `url_externa` para estas lineas y hasta ahora
        no existia columna donde ponerla en ningun servicio."""
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
    """Las dos puntas de la division tienen que contar en lo mismo.

    `unidades_a_comprar = techo(cantidad_pedida / unidades_por_empaque)` solo
    es correcta si el renglon y el producto hablan de la misma unidad. El
    producto ya tiene `unidad_base` restringida; el renglon tenia un texto
    libre de 32 caracteres sin restriccion ninguna.

    Con una punta suelta, "1 resma" contra un producto que cuenta hojas da un
    numero sin sentido y nada lo detecta. Es la misma familia de defecto que
    sumaba 12 cajas de lapices cuando la lista pedia 12 lapices: el arreglo de
    unidades queda a medias mientras una punta no este restringida.
    """

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
        """ "resma" es un empaque, no una unidad base. Si entra aqui, la
        division se hace contra hojas y el resultado no significa nada."""
        with pytest.raises(IntegrityError):
            self._item(sesion, unidad="resma")

    def test_la_unidad_puede_faltar_y_entonces_se_cuenta_por_unidad(self, sesion):
        """Nulo se admite porque muchos renglones no dicen unidad ("2
        cuadernos"), y en ese caso contar por pieza es lo correcto. Lo que no
        se admite es una unidad escrita mal."""
        assert self._item(sesion).unidad is None

    def test_la_division_de_empaque_es_expresable_de_punta_a_punta(self, sesion):
        """La prueba que amarra las dos mitades: 12 lapices contra una caja de
        12 da UNA caja, no doce."""
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
        """Un renglon que nadie supo resolver no puede quedarse callado y
        salir del kit sin que nadie se entere."""
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
        """Una tarea fallida que nadie puede atender es ruido, no un aviso."""
        sesion.add(TareaImportacion(origen="pdf", estado="fallida"))
        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_una_tarea_fallida_con_mensaje_se_acepta(self, sesion):
        sesion.add(TareaImportacion(origen="pdf", estado="fallida", error="PDF ilegible"))
        sesion.flush()
        assert sesion.query(TareaImportacion).count() == 1

    def test_la_tarea_no_guarda_el_caso_que_la_atiende(self, sesion):
        """Guardarlo metia una arista de Catalogo hacia Operacion, y era la
        unica que cerraba un ciclo en el grafo de dependencias. El Caso lo
        abre Operacion consumiendo el evento, y apunta de vuelta."""
        assert not hasattr(TareaImportacion, "caso_id")

    def test_la_etapa_completada_es_el_punto_de_reanudacion(self, sesion):
        """Reanudar desde la ultima etapa buena evita repagar la percepcion,
        que es la etapa cara."""
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
