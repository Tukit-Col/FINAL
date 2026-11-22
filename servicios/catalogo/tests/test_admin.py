from __future__ import annotations

import ast
import inspect
from typing import Any

from tukit_catalogo import admin


def _solo_codigo(funcion: Any) -> str:
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
        "marca": "Norma",
        "atributos": {"hojas": 100},
        "unidad_base": "unidad",
        "unidades_por_empaque": 1,
        "quality_score": 0.85,
        "tienda": "panamericana",
        "url": "https://ejemplo/producto",
        "precio": 650000,
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
        "atributos_clave": ["hojas", "rayado", "materias"],
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


class TestLaPaginaPinta:
    def test_pinta_el_concepto_con_su_producto(self):
        html = admin.construir([_concepto()], _resumen())
        assert "cuaderno" in html
        assert "$6.500" in html
        assert 'src="https://ejemplo/foto.jpg"' in html

    def test_cada_concepto_trae_sus_acciones_de_curaduria(self):
        html = admin.construir([_concepto()], _resumen())
        assert 'data-util="22222222-2222-2222-2222-222222222222"' in html
        assert 'data-libro="22222222-2222-2222-2222-222222222222"' in html
        assert 'data-descartar="22222222-2222-2222-2222-222222222222"' in html

    def test_un_util_sin_los_tres_niveles_se_destaca(self):
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
        html = admin.construir([_concepto()], _resumen())
        assert 'data-empaque="11111111-1111-1111-1111-111111111111"' in html

    def test_un_concepto_no_comprar_lo_dice(self):
        html = admin.construir([_concepto(tipo_item="no_comprar")], _resumen())
        assert "no se surte" in html

    def test_escapa_lo_que_viene_de_la_base(self):
        html = admin.construir([_concepto(nombre='cuaderno <malo>"x"')], _resumen())
        assert "<malo>" not in html
        assert "cuaderno &lt;malo&gt;" in html


class TestLaCuraduriaNoAbreLaPuertaDelAcudiente:
    def test_admin_no_importa_ni_usa_la_puerta(self):
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
        parametros = list(inspect.signature(admin.agregar_util).parameters)
        assert parametros[:3] == ["concepto_id", "slug", "oferta"]


class TestElServidorNoSeCaeConUnError:
    def test_los_post_estan_envueltos_en_try(self):
        cuerpo = inspect.getsource(admin._Manejador.do_POST)
        assert "try:" in cuerpo
        assert "except" in cuerpo

    def test_el_handler_de_util_reconstruye_la_oferta_desde_la_tienda(self):
        cuerpo = inspect.getsource(admin._Manejador._util)
        assert "buscar_candidatos" in cuerpo
        assert "o.sku == sku" in cuerpo


class TestEditarYBorrarUnProductoSuelto:
    def test_la_tarjeta_trae_los_datos_para_editar(self):
        html = admin.construir([_concepto()], _resumen())
        assert 'data-pid="11111111-1111-1111-1111-111111111111"' in html
        assert 'data-pnivel="confiable"' in html
        assert 'data-pprecio="6500"' in html

    def test_cada_producto_trae_editar_y_quitar(self):
        html = admin.construir([_concepto()], _resumen())
        assert 'data-editar="11111111-1111-1111-1111-111111111111"' in html
        assert 'data-borrar="11111111-1111-1111-1111-111111111111"' in html

    def test_borrar_es_un_delete_en_duro_de_las_tres_tablas(self):
        cuerpo = inspect.getsource(admin._borrar_producto)
        assert "DELETE FROM producto_canonico" in cuerpo
        assert "DELETE FROM oferta_tienda" in cuerpo
        assert "DELETE FROM precio_oferta" in cuerpo
        assert "activo=False" not in cuerpo

    def test_borrar_tambien_quita_la_propuesta_que_lo_materializo(self):
        cuerpo = inspect.getsource(admin._borrar_producto)
        assert "DELETE FROM propuesta_producto" in cuerpo
        pos_prop = cuerpo.index("DELETE FROM propuesta_producto")
        pos_prod = cuerpo.index("DELETE FROM producto_canonico WHERE id")
        assert pos_prop < pos_prod, "la propuesta se borra antes que el producto"

    def test_la_tarjeta_trae_marca_concepto_y_atributos_para_editar(self):
        html = admin.construir([_concepto()], _resumen())
        assert 'data-pmarca="Norma"' in html
        assert 'data-pconcepto="22222222-2222-2222-2222-222222222222"' in html
        assert "data-pclaves=" in html
        assert "data-pattrs=" in html

    def test_el_dialogo_ofrece_mover_a_cualquier_concepto(self):
        otro = _concepto(id="99999999-9999-9999-9999-999999999999", codigo="C031", nombre="resma")
        html = admin.construir([_concepto(), otro], _resumen())
        assert '<option value="99999999-9999-9999-9999-999999999999">C031 · resma</option>' in html

    def test_editar_actualiza_marca_concepto_y_atributos_en_el_producto(self):
        cuerpo = _solo_codigo(admin._editar_producto)
        assert '"marca"' in cuerpo
        assert '"concepto_id"' in cuerpo
        assert '"atributos"' in cuerpo
        assert "sku_interno" not in cuerpo
        assert "DELETE" not in cuerpo

    def test_editar_valida_que_el_concepto_destino_exista(self):
        cuerpo = _solo_codigo(admin._editar_producto)
        assert "FROM concepto WHERE id" in cuerpo

    def test_el_handler_de_editar_pasa_marca_concepto_y_atributos(self):
        cuerpo = inspect.getsource(admin._Manejador._editar)
        assert 'cuerpo.get("marca")' in cuerpo
        assert "concepto_id=" in cuerpo
        assert "atributos" in cuerpo

    def test_editar_precio_escribe_en_precio_oferta_no_en_el_producto(self):
        cuerpo = inspect.getsource(admin._editar_producto)
        assert "precio_oferta" in cuerpo
        assert "valor_centavos" in cuerpo

    def test_editar_y_borrar_estan_ruteados(self):
        cuerpo = inspect.getsource(admin._Manejador.do_POST)
        assert '"/editar"' in cuerpo
        assert '"/borrar"' in cuerpo

    def test_el_handler_de_editar_pasa_pesos_a_centavos(self):
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
    def test_pinta_el_candidato_con_su_precio_y_foto(self):
        h = admin.construir_cola([_grupo_cola()], 1)
        assert "FLAUTA DULCE SOPRANO HAMMELIN" in h
        assert "$18.650" in h
        assert 'src="https://ejemplo/flauta.jpg"' in h

    def test_muestra_lo_que_pidio_el_colegio_completo_y_el_isbn(self):
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
        h = admin.construir_cola([_grupo_cola()], 1)
        assert '<option value="economico" selected>' in h

    def test_el_grupo_ofrece_cerrar_el_concepto_entero(self):
        h = admin.construir_cola([_grupo_cola()], 1)
        assert 'data-nosurtir="33333333-3333-3333-3333-333333333333"' in h

    def test_un_concepto_nuevo_se_marca_y_no_ofrece_no_surtir(self):
        nuevo = admin.construir_cola([_grupo_cola(concepto_id=None, es_nuevo=True)], 1)
        real = admin.construir_cola([_grupo_cola()], 1)
        assert "concepto nuevo" in nuevo
        assert 'data-nosurtir="' not in nuevo
        assert 'data-nosurtir="' in real

    def test_cola_vacia_dice_que_hacer(self):
        h = admin.construir_cola([], 0)
        assert "La cola está vacía" in h
        assert "bd-completar" in h

    def test_escapa_lo_que_viene_de_la_base(self):
        h = admin.construir_cola([_grupo_cola(propuestas=[_propuesta_cola(nombre='x <malo>"y"')])], 1)
        assert "<malo>" not in h
        assert "&lt;malo&gt;" in h


class TestAprobarYRechazarPasanPorResolver:
    def test_aprobar_propuesta_llama_resolver_con_aprobar_true(self):
        cuerpo = inspect.getsource(admin.aprobar_propuesta)
        assert "resolver(" in cuerpo
        assert "aprobar=True" in cuerpo
        assert "producto_canonico" not in cuerpo

    def test_rechazar_propuesta_llama_resolver_con_aprobar_false(self):
        cuerpo = inspect.getsource(admin.rechazar_propuesta)
        assert "resolver(" in cuerpo
        assert "aprobar=False" in cuerpo

    def test_no_surtir_concepto_marca_no_comprar_y_descarta_pendientes(self):
        cuerpo = inspect.getsource(admin._no_surtir_concepto)
        assert 'tipo_item="no_comprar"' in cuerpo
        assert 'estado="rechazada"' in cuerpo
        assert 'estado == "pendiente"' in cuerpo

    def test_no_surtir_es_una_sola_transaccion(self):
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
