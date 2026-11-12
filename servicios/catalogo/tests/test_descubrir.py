"""Pruebas del alta de items: primero nuestro catalogo, la tienda al final.

El orden es lo que se fija aqui, y no es un detalle de implementacion. Salir
a una tienda por algo que el catalogo ya surte es no tener catalogo: la
tienda es una fuente de ALTA para lo que nos falta, nunca una fuente de
consulta para atender a un papa.
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime

import pytest
from tukit_catalogo.descubrir import (
    PuertaCerrada,
    Revision,
    _ean_valido,
    _misma_cosa,
    cabeza,
    clasificar,
    consulta_desde_renglon,
    crear_libro,
    crear_util,
    TIENDAS_LIBROS,
    consulta_libro,
    exigir_sin_revisar,
    fila_libro,
    probar,
    proponer,
    resolver,
    singular,
)


class TestElPluralNoDebeCambiarLaCosa:
    """`lapices de colores` se clasificaba como esfero, y por el plural.

    Comparando los primeros cinco caracteres, `lapices` da `lapic`: el
    sinonimo correcto `lapiz colores` no empareja y `lapicero`, de esfero, si.
    El acudiente que pide colores recibia esferos, y nada en el resultado se
    veia roto: era un producto real, con foto y con precio.
    """

    @pytest.mark.parametrize(
        ("plural", "singular_esperado"),
        [
            ("lapices", "lapiz"),
            ("luces", "luz"),
            ("colores", "color"),
            ("pinceles", "pincel"),
            ("cuadernos", "cuaderno"),
            ("pompones", "pompon"),
            # Las cortas se dejan quietas: `tres` no es el plural de `tre`.
            ("tres", "tres"),
            ("mes", "mes"),
        ],
    )
    def test_singulariza(self, plural, singular_esperado):
        assert singular(plural) == singular_esperado

    def test_lapiz_y_lapices_son_la_misma_cosa(self):
        assert _misma_cosa("lapices", "lapiz")
        assert _misma_cosa("colores", "color")

    def test_pero_lapida_no_es_un_lapiz(self):
        # El arreglo no podia ser cortar prefijos mas cortos: `lapi` habria
        # emparejado tambien esto.
        assert not _misma_cosa("lapices", "lapida")


class TestLaPuertaQueDejaSalirALaTienda:
    """Una tienda se consulta en un solo momento: revisando una lista nueva.

    El catalogo es un cache que se llena: la primera lista de un colegio paga
    sus busquedas, y al aprobarlas quedan en casa para todas las siguientes.
    Si una lista ya revisada pudiera volver a buscar, el gasto no bajaria
    nunca y el cache no seria un cache.
    """

    def test_una_lista_sin_revisar_abre_la_puerta(self):
        exigir_sin_revisar("abc123", existe=True, revisada_en=None)

    def test_una_lista_ya_revisada_no_vuelve_a_buscar(self):
        with pytest.raises(PuertaCerrada, match="ya fue revisada"):
            exigir_sin_revisar("abc123", existe=True, revisada_en=datetime(2026, 3, 1, tzinfo=UTC))

    def test_el_mensaje_dice_que_hacer_en_su_lugar(self):
        with pytest.raises(PuertaCerrada) as error:
            exigir_sin_revisar("abc123", existe=True, revisada_en=datetime(2026, 3, 1, tzinfo=UTC))
        assert "se responde con el catalogo" in str(error.value)

    def test_una_version_que_no_existe_tampoco_abre_la_puerta(self):
        with pytest.raises(PuertaCerrada, match="No existe"):
            exigir_sin_revisar("nada", existe=False, revisada_en=None)


class TestLaReglaNoDependeDeQueNadieSeEquivoque:
    """Que la tienda solo se consulte en revision es forma, no disciplina.

    Estas pruebas miran las firmas y no el comportamiento a proposito. Lo que
    protegen es que nadie pueda volver a escribir un comando que busque en
    Exito a partir de un texto suelto: para llegar al codigo que sale a la
    red hay que traer una `Revision`, y lo unico que construye una es
    `abrir_revision`, que comprueba la puerta.
    """

    def test_lo_que_sale_a_la_red_exige_una_revision(self):
        # `crear_util` sale a las tres tiendas para armar la lista de
        # candidatos, asi que cae bajo la misma regla que `crear_libro`: su
        # primer parametro es el id de la revision, no un texto suelto, y su
        # cuerpo abre la puerta antes de tocar `tiendas`.
        for funcion in (proponer, crear_libro, crear_util):
            primero = next(iter(inspect.signature(funcion).parameters.values()))
            assert primero.name in ("revision", "id_corto"), (
                f"{funcion.__name__} debe recibir la revision, no un texto libre"
            )

    def test_crear_util_abre_la_puerta_antes_de_consultar_tiendas(self):
        # El orden importa: si consultara `tiendas.buscar` antes de
        # `abrir_revision`, una lista ya revisada podria volver a gastar
        # busquedas. La puerta va primero, siempre.
        cuerpo = inspect.getsource(crear_util)
        pos_puerta = cuerpo.find("abrir_revision")
        pos_tienda = cuerpo.find("tiendas.buscar")
        assert pos_puerta != -1 and pos_tienda != -1
        assert pos_puerta < pos_tienda, "crear_util debe abrir la revision antes de salir a la tienda"

    def test_crear_util_encola_y_no_inserta_en_el_catalogo(self):
        # Un util a medio revisar no es catalogo: entra a la cola de
        # propuestas, igual que todo lo demas, y solo `resolver` --aprobar lo
        # vuelve producto. Que use `_encolar` y no toque `producto_canonico`
        # es lo que lo mantiene fuera de lo que ve el papa hasta aprobarse.
        cuerpo = inspect.getsource(crear_util)
        assert "_encolar" in cuerpo
        assert "producto_canonico" not in cuerpo

    def test_proponer_recibe_el_objeto_y_no_un_identificador(self):
        parametros = inspect.signature(proponer).parameters
        assert parametros["revision"].annotation in (Revision, "Revision")

    def test_el_match_del_acudiente_no_nombra_ninguna_tienda(self):
        # `probar` es lo que responde una lista en produccion. Si su cuerpo
        # mencionara el modulo de tiendas seria porque alguien le abrio un
        # camino a la red, y ese camino le mostraria al acudiente productos
        # que nadie verifico que podamos conseguir.
        cuerpo = inspect.getsource(probar)
        assert "tiendas." not in cuerpo
        assert "buscar_candidatos" not in cuerpo

    def test_el_modulo_del_acudiente_no_alcanza_al_que_surte(self):
        """`completar` sale a la red sin puerta, y esta bien: es curaduria.

        Llena huecos del catalogo antes de que exista un papa que pregunte, no
        durante. Pero nada en el codigo decia que fuera de curaduria, asi que
        lo unico que impedia usarlo como via de match era que nadie lo hacia.

        Esta prueba lo dice: el modulo por donde pasa una lista no puede
        importar el que consulta tiendas. Si alguien necesita surtir, corre
        `make bd-completar` aparte y despues `make bd-cargar`; lo que el papa
        ve sale de la base y de ningun otro lado.
        """
        from tukit_catalogo import descubrir

        fuente = inspect.getsource(descubrir)
        assert "import completar" not in fuente
        assert "from .completar" not in fuente


def _concepto(nombre: str, *sinonimos: str) -> dict:
    return {
        "id": uuid.uuid5(uuid.NAMESPACE_URL, nombre),
        "codigo": nombre[:4].upper(),
        "nombre": nombre,
        "sinonimos": list(sinonimos),
        "attrs": (),
    }


CATALOGO = [
    _concepto("aserrin", "aserrin de colores"),
    _concepto("colores", "lapices de colores", "colores de madera"),
    _concepto("pompones"),
    _concepto("plastilina"),
    _concepto("biblia", "biblia catolica"),
    _concepto("cuaderno", "cuaderno cosido"),
]


class TestLaCabezaDeLaFrase:
    """En espanol el nucleo va primero: lo pedido es la primera palabra."""

    def test_toma_el_sustantivo_y_no_el_adjetivo(self):
        assert cabeza("pompones de colores para manualidades") == "pompones"
        assert cabeza("3 bolsas de aserrin de colores surtidos") == "aserrin"

    def test_se_salta_la_cantidad_y_el_empaque(self):
        assert cabeza("2 paquetes de plastilina") == "plastilina"
        assert cabeza("1 cuaderno cosido de 100 hojas") == "cuaderno"

    def test_el_metro_es_una_medida_y_no_lo_pedido(self):
        """Con "metro" de cabeza, Lentejuelas ("metro lentejuelas") se llevaba
        el cable estanado de una lista de robotica."""
        assert cabeza("metro de cable estañado calibre 22") == "cable"
        assert cabeza("2 metros de lana") == "lana"

    def test_una_fraccion_no_nombra_la_cosa(self):
        assert cabeza("paquete de (1/8 cartulina) color amarillo") == "cartulina"


class TestClasificarContraNuestroCatalogo:
    def test_reconoce_lo_que_ya_sabemos_que_es(self):
        _, nombre, puntaje = clasificar("3 bolsas de aserrin de colores", CATALOGO)
        assert nombre == "aserrin"
        # El puntaje no llega a 1.0 y no debe: acertar la cabeza da el piso
        # de 0.6 y lo que sobra de la frase gradua el resto. Es lo que permite
        # que `lapiz colores` le gane a `lapiz` cuando piden colores, y por
        # eso lo que se afirma aqui es que reconoce, no un numero exacto.
        assert puntaje > 0.5

    def test_de_colores_es_un_adjetivo_y_no_el_concepto_colores(self):
        """El error que se veia feo: `pompones de colores` y `chaquiras de
        colores` caian los dos en el concepto de los lapices de colores,
        porque la palabra estaba contenida en la frase. Ahi `colores` es un
        adjetivo, no lo que el colegio pide."""
        _, nombre, _ = clasificar("pompones de colores para manualidades", CATALOGO)
        assert nombre == "pompones"

    def test_lo_que_no_tenemos_no_se_fuerza_dentro_de_lo_que_si(self):
        """`chaquiras` no esta en el catalogo. Es preferible reconocerlo como
        concepto nuevo, que una persona fusiona en un minuto, a colgarlo de
        plastilina porque se parecian un poco."""
        _, _, puntaje = clasificar("chaquiras de colores", CATALOGO)
        assert puntaje < 0.5

    def test_encuentra_por_sinonimo(self):
        _, nombre, _ = clasificar("biblia catolica letra grande", CATALOGO)
        assert nombre == "biblia"

    def test_tolera_el_plural_y_el_singular(self):
        """`lapices` tiene que encontrar `lapiz` y al reves: el colegio
        escribe en plural y el catalogo nombra en singular."""
        _, nombre, _ = clasificar("2 cuadernos cosidos", CATALOGO)
        assert nombre == "cuaderno"

    def test_un_rango_de_durezas_es_el_kit_de_dibujo(self):
        """`Lapiz 2H-6B` pide la serie, no un lapiz 2H: caia en el lapiz suelto,
        exigia la dureza 2H y se quedaba sin opcion."""
        conceptos = [
            {"id": uuid.uuid4(), "nombre": "lapiz", "sinonimos": ["lapiz negro"]},
            {"id": uuid.uuid4(), "nombre": "kit de lapices de dibujo", "sinonimos": ["lapiz serie durezas"]},
        ]

        for renglon in ("Lápiz 2H-6B", "Lápices 2B a 6B", "lapiz 4H - 8B", "Lápices HB, 2H, 2B, 6B"):
            assert clasificar(renglon, conceptos)[1] == "kit de lapices de dibujo", renglon
        assert clasificar("Lápiz negro HB", conceptos)[1] == "lapiz"

    def test_un_par_de_escuadras_es_el_juego(self):
        """Los numeros no cuentan en el parecido: `escuadras 30° y 45°` empataba
        con `escuadras` y ganaba la escuadra suelta."""
        conceptos = [
            {"id": uuid.uuid4(), "nombre": "escuadra", "sinonimos": ["escuadras", "escuadra grado"]},
            {"id": uuid.uuid4(), "nombre": "juego de geometria", "sinonimos": ["escuadras juego"]},
        ]

        for renglon in ("escuadras 30° y 45°", "Escuadras de 45 y 60 grados", "2 escuadras 45° - 60°"):
            assert clasificar(renglon, conceptos)[1] == "juego de geometria", renglon
        assert clasificar("escuadra de 45 grados", conceptos)[1] == "escuadra"


class TestLaConsultaQueSeLeMandaALaTienda:
    """Solo se construye para lo que NO tenemos, y describe QUE, no CUANTO."""

    def test_quita_cantidades_y_empaques(self):
        assert consulta_desde_renglon("3 bolsas de aserrin de colores surtidos") == "aserrin colores surtidos"
        assert consulta_desde_renglon("2 paquetes de plastilina") == "plastilina"

    def test_conserva_los_adjetivos_que_discriminan(self):
        """`de colores` separa el aserrin escolar del de carpinteria: quitar
        todos los adjetivos haria la consulta inutil."""
        assert "colores" in consulta_desde_renglon("aserrin de colores")

    def test_quita_las_medidas(self):
        assert consulta_desde_renglon("vinilo de 250 gr azul") == "vinilo azul"


class TestElEanQueTraeLaTiendaSoloEntraSiEsUno:
    """Una tienda pone cualquier cosa en el campo EAN: un SKU, un vacio."""

    @pytest.mark.parametrize("bueno", ["12345678", "123456789012", "1234567890123"])
    def test_acepta_8_12_o_13_digitos(self, bueno):
        assert _ean_valido(bueno) == bueno

    @pytest.mark.parametrize("malo", [None, "", "  ", "123", "SKU-4451", "12a45678", "12345678901234"])
    def test_descarta_lo_que_no_parece_un_ean(self, malo):
        assert _ean_valido(malo) is None


class TestDescartarPuedeCerrarElConcepto:
    """Rechazar tiene dos sabores y solo uno toca el concepto."""

    def test_solo_con_no_surtir_se_marca_no_comprar(self):
        # El rechazo corriente descarta la propuesta y deja el concepto
        # abierto; con --no-surtir el concepto pasa a 'no_comprar'. Que la
        # marca cuelgue de esa bandera, y no del rechazo a secas, es lo que
        # evita cerrar un concepto por descartar un mal candidato.
        cuerpo = inspect.getsource(resolver)
        marca = cuerpo.find('tipo_item="no_comprar"')
        guarda = cuerpo.find("if no_surtir")
        assert marca != -1 and guarda != -1
        assert guarda < marca, "marcar no_comprar debe estar guardado por no_surtir"

    def test_no_surtir_es_opcional_para_no_romper_el_rechazo_corriente(self):
        assert inspect.signature(resolver).parameters["no_surtir"].default is False


class TestLibrosEnBuscalibreYLibreriaNacional:
    def test_fila_libro_normaliza_precio_colombiano(self):
        fila = fila_libro("buscalibre", {"titulo": "Nacho", "isbn13": "9789580714729", "precio": "$ 54.900"})
        assert fila["precio"] == "54900"

    def test_fila_libro_sin_imagen_se_marca(self):
        fila = fila_libro("libreria_nacional", {"titulo": "Nacho", "imagen_url": None})
        assert fila["imagen_url"] == ""
        assert set(fila) == {"titulo", "isbn13", "editorial", "precio", "imagen_url", "url_origen"}

    def test_consulta_libro_codifica_tildes_y_espacios(self):
        url = consulta_libro("Álgebra de Baldor", None)
        assert " " not in url and "Á" not in url
        assert url.startswith(TIENDAS_LIBROS["buscalibre"])
        assert "9789580714729" in consulta_libro("x", "9789580714729")
