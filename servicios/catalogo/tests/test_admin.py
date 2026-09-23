"""Pruebas del front de administracion (`admin`).

Dos clases de prueba conviven aqui, y por la misma razon que en
`test_descubrir`: lo que toca la base corre contra Postgres real (via
`crear_motor`), asi que no se ejerce con la sesion SQLite, se afirma leyendo el
codigo fuente. Lo que es puro --pintar el HTML, formatear un precio, validar un
EAN-- si se ejerce de verdad, con diccionarios armados a mano que imitan lo que
`_leer` saca de la base.

Lo que estas pruebas protegen, mas alla de que el HTML salga: que la curaduria
por esta pantalla entre por los MISMOS seams que el resto del catalogo
(`_encolar` + `resolver`), y que NO abra la puerta del acudiente. Un alta a mano
no puede ser un atajo que se salte la cola de propuestas ni que le abra un
camino a las tiendas al flujo del papa.
"""

from __future__ import annotations

import ast
import inspect
from typing import Any

import pytest
from tukit_catalogo import admin


def _solo_codigo(funcion: Any) -> str:
    """La fuente de una funcion sin su docstring y sin sus comentarios.

    Afirmar sobre el codigo fuente es util cuando lo que se protege es una
    decision de implementacion que no se puede ejercer sin Postgres, pero
    tiene un modo de fallar propio: la prosa que EXPLICA la decision menciona
    lo mismo que la prueba prohibe, y entonces la prueba castiga documentar.
    Ya paso con `activo=False`.
    """
    arbol = ast.parse(inspect.getsource(funcion))
    definicion = arbol.body[0]
    cuerpo = definicion.body[1:] if ast.get_docstring(definicion) else definicion.body
    lineas = inspect.getsource(funcion).splitlines()
    primera = cuerpo[0].lineno - definicion.lineno
    return "\n".join(linea for linea in lineas[primera:] if not linea.lstrip().startswith("#"))


def _producto(**kw: Any) -> dict[str, Any]:
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "nombre": "Cuaderno cosido 100 hojas",
        "nivel": "confiable",
        "imagen_url": "https://ejemplo/foto.jpg",
        "personaje": None,
        "atributos": {"hojas": 100},
        "unidad_base": "unidad",
        "unidades_por_empaque": 1,
        "quality_score": 0.85,
        "tienda": "panamericana",
        "url": "https://ejemplo/producto",
        "precio": 650000,  # centavos
    }
    base.update(kw)
    return base


def _concepto(**kw: Any) -> dict[str, Any]:
    base = {
        "id": "22222222-2222-2222-2222-222222222222",
        "codigo": "C001",
        "nombre": "cuaderno",
        "tipo_item": "util",
        "demanda": 12,
        "sinonimos": ["cuaderno cosido"],
        "productos": [_producto()],
    }
    base.update(kw)
    return base


class TestElPrecioSeVeEnPesos:
    def test_convierte_centavos_a_pesos_con_separador(self):
        assert admin._pesos(650000) == "$6.500"
        assert admin._pesos(1540000) == "$15.400"

    def test_sin_precio_lo_dice(self):
        assert admin._pesos(None) == "sin precio"
        assert admin._pesos(0) == "sin precio"


class TestElEanQueTraeLaTiendaSoloEntraSiEsUno:
    @pytest.mark.parametrize("bueno", ["12345678", "123456789012", "1234567890123"])
    def test_acepta_8_12_o_13_digitos(self, bueno):
        assert admin._ean_valido(bueno) == bueno

    @pytest.mark.parametrize("malo", [None, "", "  ", "123", "SKU-4451", "12a45678"])
    def test_descarta_lo_que_no_parece_un_ean(self, malo):
        assert admin._ean_valido(malo) is None


class TestLaPaginaPinta:
    """`construir` arma la pagina entera desde los mismos dicts que `_leer` da."""

    def test_pinta_el_concepto_con_su_producto(self):
        html = admin.construir([_concepto()], _resumen())
        assert "cuaderno" in html
        assert "$6.500" in html
        assert 'src="https://ejemplo/foto.jpg"' in html

    def test_cada_concepto_trae_sus_acciones_de_curaduria(self):
        # +Util, +Libro y Descartar cuelgan del id del concepto: sin eso la
        # pantalla seria de solo lectura, que es lo que `vista` ya hace.
        html = admin.construir([_concepto()], _resumen())
        assert 'data-util="22222222-2222-2222-2222-222222222222"' in html
        assert 'data-libro="22222222-2222-2222-2222-222222222222"' in html
        assert 'data-descartar="22222222-2222-2222-2222-222222222222"' in html

    def test_un_util_sin_los_tres_niveles_se_destaca(self):
        # El objetivo de la pantalla es cerrar huecos; un comprable incompleto
        # tiene que saltar a la vista. Se mira la clase del <section>, no la
        # palabra suelta: `destacado` tambien vive en el CSS.
        html = admin.construir([_concepto()], _resumen())
        assert 'class="concepto destacado"' in html

    def test_un_util_completo_no_se_destaca(self):
        completo = _concepto(
            productos=[
                _producto(nivel="economico"),
                _producto(nivel="confiable"),
                _producto(nivel="premium"),
            ]
        )
        html = admin.construir([completo], _resumen())
        assert 'class="concepto destacado"' not in html

    def test_el_empaque_es_editable(self):
        # El combo de 12 borradores vive aqui: unidades_por_empaque tiene que
        # ser un input que se pueda corregir, no un texto.
        html = admin.construir([_concepto()], _resumen())
        assert 'data-empaque="11111111-1111-1111-1111-111111111111"' in html

    def test_un_concepto_no_comprar_lo_dice(self):
        html = admin.construir([_concepto(tipo_item="no_comprar")], _resumen())
        assert "no se surte" in html

    def test_escapa_lo_que_viene_de_la_base(self):
        # Un nombre con < o " no puede romper el HTML: sale escapado. El
        # <script> del guion es legitimo; lo que se afirma es que el nombre
        # inyectado NO aparece crudo, sino con sus entidades.
        html = admin.construir([_concepto(nombre='cuaderno <malo>"x"')], _resumen())
        assert "<malo>" not in html
        assert "cuaderno &lt;malo&gt;" in html


class TestLaCuraduriaNoAbreLaPuertaDelAcudiente:
    """El alta a mano es curaduria proactiva, como `completar`: sin puerta.

    Pero justo por eso no puede tocar el flujo del papa. Estas pruebas leen el
    codigo: `admin` no importa la puerta ni la usa, y su alta pasa por los
    mismos seams (`_encolar` + `resolver`) que aprueban lo que llega de una
    lista, no por un insert propio a `producto_canonico`.
    """

    def test_admin_no_importa_ni_usa_la_puerta(self):
        # Se mira el codigo sin comentarios ni docstrings: la palabra
        # `abrir_revision` aparece en el docstring del modulo explicando
        # justamente por que NO se usa, y eso no es usarla. Lo que no puede
        # pasar es importarla o llamarla.
        arbol = ast.parse(inspect.getsource(admin))
        nombres_puerta = {"abrir_revision", "exigir_sin_revisar", "PuertaCerrada"}
        importados = {
            alias.name for nodo in ast.walk(arbol) if isinstance(nodo, ast.ImportFrom) for alias in nodo.names
        }
        assert not (importados & nombres_puerta), "admin no debe importar la puerta del acudiente"
        llamadas = {
            nodo.func.id
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)
        }
        assert not (llamadas & nombres_puerta), "admin no debe llamar la puerta del acudiente"

    def test_agregar_util_encola_y_aprueba_no_inserta_a_mano(self):
        cuerpo = inspect.getsource(admin.agregar_util)
        assert "_encolar" in cuerpo
        assert "resolver" in cuerpo
        assert "producto_canonico" not in cuerpo

    def test_agregar_libro_encola_y_aprueba_no_inserta_a_mano(self):
        cuerpo = inspect.getsource(admin.agregar_libro)
        assert "_encolar" in cuerpo
        assert "resolver" in cuerpo
        assert "producto_canonico" not in cuerpo

    def test_el_util_se_aprueba_por_el_sku_que_eligio_la_persona(self):
        # `agregar_util` recibe una Oferta ya elegida, no un texto libre: el
        # primer parametro es el concepto y el tercero la oferta.
        parametros = list(inspect.signature(admin.agregar_util).parameters)
        assert parametros[:3] == ["concepto_id", "slug", "oferta"]


class TestElServidorNoSeCaeConUnError:
    """Un fallo en un handler devuelve 500 JSON, no tumba el proceso."""

    def test_los_post_estan_envueltos_en_try(self):
        cuerpo = inspect.getsource(admin._Manejador.do_POST)
        assert "try:" in cuerpo
        assert "except" in cuerpo

    def test_el_handler_de_util_reconstruye_la_oferta_desde_la_tienda(self):
        # No confia en la Oferta que arme el navegador: vuelve a buscar y toma
        # la oferta por sku. Asi el precio y la ficha salen de la tienda.
        cuerpo = inspect.getsource(admin._Manejador._util)
        assert "buscar_candidatos" in cuerpo
        assert "o.sku == sku" in cuerpo


class TestEditarYBorrarUnProductoSuelto:
    """Curar duplicados y basura: editar un producto o quitarlo del catalogo.

    La pantalla no era editable a nivel de producto --solo empaque y acciones de
    concepto-- y por eso los duplicados (cuaderno x17) y la basura no-infantil
    (morral universitario en un concepto de ninos) no se podian limpiar desde
    aqui. Estas pruebas fijan el contrato: el producto trae los datos para
    editarlo, hay boton de editar y de quitar, quitar es un DELETE en duro (no un
    `activo=False`, porque `volcar` exporta todo `producto_canonico` sin mirar
    `activo` y un desactivado ensuciaria el CSV curado), y ambos handlers estan
    ruteados.
    """

    def test_la_tarjeta_trae_los_datos_para_editar(self):
        # El dialogo de editar se llena desde data-attributes de la tarjeta: sin
        # ellos el navegador no sabe que nombre/precio/nivel/foto precargar.
        html = admin.construir([_concepto()], _resumen())
        assert 'data-pid="11111111-1111-1111-1111-111111111111"' in html
        assert 'data-pnivel="confiable"' in html
        assert 'data-pprecio="6500"' in html  # 650000 centavos -> 6500 pesos

    def test_cada_producto_trae_editar_y_quitar(self):
        html = admin.construir([_concepto()], _resumen())
        assert 'data-editar="11111111-1111-1111-1111-111111111111"' in html
        assert 'data-borrar="11111111-1111-1111-1111-111111111111"' in html

    def test_borrar_es_un_delete_en_duro_de_las_tres_tablas(self):
        # Quitar del catalogo BORRA en duro producto, oferta y precio: `volcar`
        # exporta todo `producto_canonico` sin mirar `activo`, asi que un
        # `activo=False` seguiria en el CSV curado. Para dejar el corpus limpio
        # el producto tiene que desaparecer de la base, con sus hijos.
        cuerpo = inspect.getsource(admin._borrar_producto)
        assert "DELETE FROM producto_canonico" in cuerpo
        assert "DELETE FROM oferta_tienda" in cuerpo
        assert "DELETE FROM precio_oferta" in cuerpo
        assert "activo=False" not in cuerpo

    def test_borrar_tambien_quita_la_propuesta_que_lo_materializo(self):
        # Un producto que nacio de aprobar una propuesta deja esa fila
        # apuntandolo. La FK la pondria en NULL al borrar el producto, pero el
        # CHECK `propuesta_aprobada_tiene_producto` prohibe una propuesta
        # aprobada sin producto: sin borrar la propuesta antes, el DELETE del
        # producto revienta. Se borra la propuesta ANTES que el producto.
        cuerpo = inspect.getsource(admin._borrar_producto)
        assert "DELETE FROM propuesta_producto" in cuerpo
        pos_prop = cuerpo.index("DELETE FROM propuesta_producto")
        pos_prod = cuerpo.index("DELETE FROM producto_canonico WHERE id")
        assert pos_prop < pos_prod, "la propuesta se borra antes que el producto"

    def test_editar_precio_escribe_en_precio_oferta_no_en_el_producto(self):
        # Nombre/nivel/foto viven en producto_canonico; el precio vive en
        # precio_oferta. Editar el precio tiene que ir a esa tabla.
        cuerpo = inspect.getsource(admin._editar_producto)
        assert "precio_oferta" in cuerpo
        assert "valor_centavos" in cuerpo

    def test_editar_y_borrar_estan_ruteados(self):
        cuerpo = inspect.getsource(admin._Manejador.do_POST)
        assert '"/editar"' in cuerpo
        assert '"/borrar"' in cuerpo

    def test_el_handler_de_editar_pasa_pesos_a_centavos(self):
        # El navegador manda pesos; la base guarda centavos. El handler multiplica.
        cuerpo = inspect.getsource(admin._Manejador._editar)
        assert "* 100" in cuerpo


def _propuesta_cola(**kw: Any) -> dict[str, Any]:
    base = {
        "id": "aaaaaaaa-1111-1111-1111-111111111111",
        "id_corto": "aaaaaaaa",
        "texto_origen": "flauta dulce soprano",
        "nombre": "FLAUTA DULCE SOPRANO HAMMELIN",
        "precio": 1865000,
        "nivel_sugerido": "economico",
        "ean": "9789584280850",
        "marca": "Hammelin",
        "imagen_url": "https://ejemplo/flauta.jpg",
        "url": "https://ejemplo/flauta",
        "puntaje": 0.4,
        "origen": "scraper",
        "tienda": "exito",
    }
    base.update(kw)
    return base


def _grupo_cola(**kw: Any) -> dict[str, Any]:
    base = {
        "codigo": "C066",
        "concepto_id": "33333333-3333-3333-3333-333333333333",
        "nombre": "flauta",
        "demanda": 5,
        "es_nuevo": False,
        "propuestas": [_propuesta_cola()],
    }
    base.update(kw)
    return base


class TestLaColaDeRevisionPinta:
    """`construir_cola` arma la cola desde los dicts que da `_leer_cola`."""

    def test_pinta_el_candidato_con_su_precio_y_foto(self):
        h = admin.construir_cola([_grupo_cola()], 1)
        assert "FLAUTA DULCE SOPRANO HAMMELIN" in h
        assert "$18.650" in h
        assert 'src="https://ejemplo/flauta.jpg"' in h

    def test_muestra_lo_que_pidio_el_colegio_completo_y_el_isbn(self):
        # Para un libro el nombre de la tienda suele empezar por la editorial y
        # el formato ("Debolsillo, Rustica, 136 pags."), no por el titulo. La
        # persona casa la edicion contra lo que pidio el colegio (`texto_origen`,
        # completo, no recortado) y confirma con el ISBN: ambos tienen que verse.
        h = admin.construir_cola(
            [_grupo_cola(propuestas=[_propuesta_cola(texto_origen="Cronica de una muerte anunciada")])], 1
        )
        assert "pidieron: <b>Cronica de una muerte anunciada</b>" in h
        assert "ISBN 9789584280850" in h

    def test_cada_candidato_trae_aprobar_y_descartar(self):
        h = admin.construir_cola([_grupo_cola()], 1)
        assert 'data-aprobar="aaaaaaaa"' in h
        assert 'data-rechazar="aaaaaaaa"' in h

    def test_el_nivel_sugerido_viene_seleccionado(self):
        # El candidato barato que la consulta puso en 'economico' llega con ese
        # nivel preseleccionado, pero editable: la persona manda.
        h = admin.construir_cola([_grupo_cola()], 1)
        assert '<option value="economico" selected>' in h

    def test_el_grupo_ofrece_cerrar_el_concepto_entero(self):
        h = admin.construir_cola([_grupo_cola()], 1)
        assert 'data-nosurtir="33333333-3333-3333-3333-333333333333"' in h

    def test_un_concepto_nuevo_se_marca_y_no_ofrece_no_surtir(self):
        # Sin concepto_id no hay concepto que cerrar: el boton no aparece. Se
        # compara contra el grupo con concepto real, que SI trae el boton, para
        # no chocar con el `data-nosurtir` que vive tambien en el guion (JS).
        nuevo = admin.construir_cola([_grupo_cola(concepto_id=None, es_nuevo=True)], 1)
        real = admin.construir_cola([_grupo_cola()], 1)
        assert "concepto nuevo" in nuevo
        assert 'data-nosurtir="' not in nuevo  # el boton del grupo no se pinta
        assert 'data-nosurtir="' in real  # el del grupo con concepto real, si

    def test_cola_vacia_dice_que_hacer(self):
        h = admin.construir_cola([], 0)
        assert "La cola está vacía" in h
        assert "bd-completar" in h

    def test_escapa_lo_que_viene_de_la_base(self):
        h = admin.construir_cola([_grupo_cola(propuestas=[_propuesta_cola(nombre='x <malo>"y"')])], 1)
        assert "<malo>" not in h
        assert "&lt;malo&gt;" in h


class TestAprobarYRechazarPasanPorResolver:
    """La cola no reimplementa el alta: reusa `resolver`, el seam de siempre."""

    def test_aprobar_propuesta_llama_resolver_con_aprobar_true(self):
        cuerpo = inspect.getsource(admin.aprobar_propuesta)
        assert "resolver(" in cuerpo
        assert "aprobar=True" in cuerpo
        assert "producto_canonico" not in cuerpo  # no inserta a mano

    def test_rechazar_propuesta_llama_resolver_con_aprobar_false(self):
        cuerpo = inspect.getsource(admin.rechazar_propuesta)
        assert "resolver(" in cuerpo
        assert "aprobar=False" in cuerpo

    def test_no_surtir_concepto_marca_no_comprar_y_descarta_pendientes(self):
        # Cerrar un concepto y limpiar su cola van juntos: si el concepto no se
        # surte, sus candidatos pendientes no pueden reaparecer.
        cuerpo = inspect.getsource(admin._no_surtir_concepto)
        assert 'tipo_item="no_comprar"' in cuerpo
        assert 'estado="rechazada"' in cuerpo
        assert 'estado == "pendiente"' in cuerpo

    def test_no_surtir_es_una_sola_transaccion(self):
        # Marcar el concepto y descartar sus propuestas tiene que ser atomico:
        # un concepto no_comprar con candidatos vivos es un estado a medias.
        cuerpo = inspect.getsource(admin._no_surtir_concepto)
        assert "async with motor.engine.begin() as conexion" in cuerpo


class TestLaColaSeSirveYSeRutea:
    def test_get_cola_esta_ruteada(self):
        cuerpo = inspect.getsource(admin._Manejador.do_GET)
        assert '"/cola"' in cuerpo
        assert "_leer_cola" in cuerpo

    def test_los_post_de_cola_estan_despachados(self):
        cuerpo = inspect.getsource(admin._Manejador.do_POST)
        assert '"/cola-aprobar"' in cuerpo
        assert '"/cola-rechazar"' in cuerpo


def _resumen() -> dict[str, int]:
    return {
        "productos": 1,
        "conceptos": 1,
        "comprables": 1,
        "completos": 0,
        "sin_producto": 0,
        "con_foto": 1,
        "tiendas": 3,
        "por_revisar": 0,
        "por_revisar_cola": 0,
    }
