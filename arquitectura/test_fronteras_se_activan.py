from __future__ import annotations

import ast

from test_fronteras import (
    DUENO_DE_TABLA,
    REFERENCIAS_DECLARADAS,
    SERVICIOS,
    _buscar_ciclo,
    _cadenas_no_docstring,
    _columnas_declaradas,
    _hablan_con_redis,
    _modulos_importados,
    _revisar_lectura_cruzada,
    _tabla_apuntada,
    _tablas_declaradas,
)


def _arbol(fuente: str) -> ast.Module:
    return ast.parse(fuente)


def test_detecta_importacion_de_otro_servicio():
    arbol = _arbol("from tukit_catalogo.models import ProductoCanonico")
    modulos = _modulos_importados(arbol)
    raices = {m.split(".")[0] for m in modulos}
    paquetes_ajenos = {s.paquete for s in SERVICIOS.values() if s.nombre != "comercio"}
    assert raices & paquetes_ajenos, "No detecto la importacion de un paquete ajeno."


def test_detecta_importacion_absoluta_simple():
    arbol = _arbol("import tukit_identidad")
    assert "tukit_identidad" in _modulos_importados(arbol)


def test_no_marca_como_ajena_una_importacion_de_libreria_compartida():
    arbol = _arbol("from tukit_comun.redaccion import anonimizar_nombres")
    raices = {m.split(".")[0] for m in _modulos_importados(arbol)}
    paquetes = {s.paquete for s in SERVICIOS.values()}
    assert not (raices & paquetes), "`libs/` no debe contar como servicio ajeno."


def test_detecta_la_tabla_ajena_declarada():
    fuente = """
class ProductoCanonico(Base):
    __tablename__ = "producto_canonico"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
"""
    declaradas = _tablas_declaradas(_arbol(fuente))
    assert declaradas, "No encontro ningun __tablename__."

    tabla, _linea = declaradas[0]
    assert DUENO_DE_TABLA[tabla] == "catalogo"
    assert tabla not in SERVICIOS["comercio"].tablas


def test_detecta_tabla_que_no_existe_en_el_manifiesto():
    fuente = """
class Invento(Base):
    __tablename__ = "tabla_que_nadie_diseno"
"""
    tabla, _ = _tablas_declaradas(_arbol(fuente))[0]
    assert tabla not in DUENO_DE_TABLA


def test_acepta_la_tabla_propia():
    fuente = """
class Pedido(Base):
    __tablename__ = "pedido"
"""
    tabla, _ = _tablas_declaradas(_arbol(fuente))[0]
    assert tabla in SERVICIOS["comercio"].tablas


def test_la_bandeja_de_salida_es_valida_en_todos_los_servicios():
    for servicio in SERVICIOS.values():
        if servicio.base_datos:
            assert "bandeja_salida" in servicio.tablas, (
                f"`{servicio.nombre}` tiene base propia y no declara bandeja_salida."
            )
    assert "bandeja_salida" not in DUENO_DE_TABLA, "Una tabla replicada no debe tener dueno unico."


def test_detecta_la_base_ajena_en_una_cadena_de_conexion():
    fuente = 'DSN = "postgresql+asyncpg://tukit:tukit@localhost/tukit_operacion"'
    cadenas = _cadenas_no_docstring(_arbol(fuente))
    assert any("tukit_operacion" in c for c in cadenas), (
        "No detecto la base ajena en una cadena de conexion literal."
    )


def test_no_marca_el_nombre_del_paquete_hermano_en_un_docstring():
    fuente = '''
async def _publicar_evento(conexion, trabajo_id):
    """Deja el evento en la bandeja.

    El repartidor de Operacion (`tukit_operacion.repartidor`) lo drena y avisa.
    """
    return None
'''
    cadenas = _cadenas_no_docstring(_arbol(fuente))
    assert not any("tukit_operacion" in c for c in cadenas), (
        "Un docstring que nombra el paquete hermano no debe contar como conexion a su base."
    )


def test_no_marca_el_nombre_de_la_base_ajena_en_un_comentario():
    fuente = "x = 1  # ojo: esto NO habla con tukit_catalogo\n"
    cadenas = _cadenas_no_docstring(_arbol(fuente))
    assert not any("tukit_catalogo" in c for c in cadenas), (
        "Un comentario no debe contar como conexion a la base ajena."
    )


_POLLER_BIEN = """
from tukit_comun.config import url_desde_entorno

def _motor_lectura(servicio):
    return create_async_engine(url_desde_entorno(servicio))

async def correr_una_vez():
    motor = _motor_lectura("catalogo")
    return await Poller(motor_catalogo=motor).pasada()

async def escuchar_cola(url, *, seguir):
    poller = Poller(motor_catalogo=None)
    return await consumir(url, Consumidor(cola=COLEGIOS, manejar=poller.manejar), seguir=seguir)

class Poller:
    async def manejar(self, evento):
        return await self._procesar(None, evento)

    async def _procesar(self, conexion, fila):
        return Resultado.HECHO
"""
_DECLARADA = {"modulo": "tukit_identidad.poller", "modo": "sin_broker"}


def test_acepta_la_lectura_cruzada_que_es_solo_respaldo():
    assert _revisar_lectura_cruzada("tukit_identidad.poller", _arbol(_POLLER_BIEN), _DECLARADA) == []


def test_detecta_la_lectura_cruzada_sin_declarar():
    problemas = _revisar_lectura_cruzada("tukit_comercio.espia", _arbol(_POLLER_BIEN), None)
    assert len(problemas) == 1
    assert "no esta en `[[lecturas_cruzadas]]`" in problemas[0]


def test_detecta_la_lectura_cruzada_declarada_en_otro_modo():
    problemas = _revisar_lectura_cruzada(
        "tukit_identidad.poller", _arbol(_POLLER_BIEN), {**_DECLARADA, "modo": "siempre"}
    )
    assert any("solo vale" in p for p in problemas)


def test_detecta_el_modulo_sin_camino_con_broker():
    fuente = _POLLER_BIEN.replace("async def escuchar_cola", "async def escuchar_otra_cosa")
    problemas = _revisar_lectura_cruzada("tukit_identidad.poller", _arbol(fuente), _DECLARADA)
    assert any("no tiene `escuchar_cola`" in p for p in problemas)


def test_detecta_el_camino_con_broker_que_llega_al_motor_ajeno():
    fuente = _POLLER_BIEN.replace(
        "        return await self._procesar(None, evento)",
        '        _motor_lectura("catalogo")\n        return await self._procesar(None, evento)',
    )
    problemas = _revisar_lectura_cruzada("tukit_identidad.poller", _arbol(fuente), _DECLARADA)
    assert len(problemas) == 1
    assert "llega a una lectura cruzada por _motor_lectura" in problemas[0]


def test_detecta_el_motor_ajeno_abierto_dentro_de_escuchar_cola():
    fuente = _POLLER_BIEN.replace(
        "    poller = Poller(motor_catalogo=None)",
        '    poller = Poller(motor_catalogo=create_async_engine(url_desde_entorno("catalogo")))',
    )
    problemas = _revisar_lectura_cruzada("tukit_identidad.poller", _arbol(fuente), _DECLARADA)
    assert any("llega a una lectura cruzada por escuchar_cola" in p for p in problemas)


def test_detecta_referencia_cruzada_sin_declarar():
    fuente = """
class Devolucion(Base):
    __tablename__ = "devolucion"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    estudiante_id: Mapped[uuid.UUID] = mapped_column()
"""
    columnas = _columnas_declaradas(_arbol(fuente))
    cruzadas = [
        (tabla, col)
        for tabla, col, _ in columnas
        if col.endswith("_id") and DUENO_DE_TABLA.get(col[:-3]) not in (None, "comercio")
    ]
    assert cruzadas == [("devolucion", "estudiante_id")], (
        "No detecto que `devolucion.estudiante_id` apunta a `estudiante`, de Identidad."
    )
    assert "comercio.devolucion.estudiante_id" not in REFERENCIAS_DECLARADAS


def test_detecta_la_columna_de_actor_que_no_termina_en_id():
    fuente = """
class Informe(Base):
    __tablename__ = "informe"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    firmado_por: Mapped[uuid.UUID] = mapped_column()
"""
    _, columna, _ = _columnas_declaradas(_arbol(fuente))[1]
    assert _tabla_apuntada(columna) == "usuario", "No reconocio `firmado_por` como referencia a `usuario`."
    assert DUENO_DE_TABLA["usuario"] == "identidad"
    assert "comercio.informe.firmado_por" not in REFERENCIAS_DECLARADAS


def test_no_confunde_una_columna_cualquiera_con_una_referencia():
    for columna in ("creado_en", "nombre", "activo", "valor_centavos"):
        assert _tabla_apuntada(columna) is None, f"`{columna}` se tomo por referencia."


def test_acepta_la_referencia_cruzada_ya_declarada():
    fuente = """
class LineaPedido(Base):
    __tablename__ = "linea_pedido"
    matricula_id: Mapped[uuid.UUID] = mapped_column()
"""
    _, columna, _ = _columnas_declaradas(_arbol(fuente))[0]
    assert f"comercio.linea_pedido.{columna}" in REFERENCIAS_DECLARADAS


def test_no_marca_la_llave_primaria_ni_la_referencia_local():
    fuente = """
class LineaPedido(Base):
    __tablename__ = "linea_pedido"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    pedido_id: Mapped[uuid.UUID] = mapped_column()
"""
    for _tabla, columna, _ in _columnas_declaradas(_arbol(fuente)):
        if columna.endswith("_id"):
            dueno = DUENO_DE_TABLA.get(columna[:-3])
            assert dueno in (None, "comercio"), f"`{columna}` se marco como ajena y es local."


def test_ignora_las_anotaciones_fuera_de_una_clase_con_tablename():
    fuente = """
class RespuestaPedido(BaseModel):
    matricula_id: uuid.UUID
"""
    assert _columnas_declaradas(_arbol(fuente)) == []


def test_detecta_el_ciclo_real_que_existio():
    grafo = {
        "identidad": set(),
        "catalogo": {"identidad", "operacion"},
        "operacion": {"identidad", "catalogo"},
    }
    ciclo = _buscar_ciclo(grafo)
    assert ciclo is not None, "No detecto el ciclo catalogo <-> operacion."
    assert ciclo[0] == ciclo[-1], "El ciclo devuelto no cierra sobre si mismo."
    assert set(ciclo) == {"catalogo", "operacion"}


def test_no_marca_ciclo_donde_solo_hay_un_destino_compartido():
    grafo = {
        "identidad": set(),
        "catalogo": {"identidad"},
        "comercio": {"identidad", "catalogo"},
        "inteligencia": {"identidad", "catalogo"},
    }
    assert _buscar_ciclo(grafo) is None


def test_detecta_el_ciclo_largo_y_no_solo_el_de_dos():
    grafo = {
        "identidad": {"comercio"},
        "catalogo": {"identidad"},
        "comercio": {"catalogo"},
    }
    ciclo = _buscar_ciclo(grafo)
    assert ciclo is not None
    assert len(set(ciclo)) == 3


def test_un_servicio_que_se_referencia_a_si_mismo_no_cuenta():
    assert _buscar_ciclo({"catalogo": {"catalogo"}, "identidad": set()}) is None


def test_detecta_cada_forma_de_traer_redis():
    for fuente in (
        "import redis",
        "import redis.asyncio as redis_asincrono",
        "from redis.asyncio import Redis",
        "from redis import exceptions",
        "redis_asincrono = pytest.importorskip('redis.asyncio')",
        "modulo = importlib.import_module('redis')",
        "def f():\n    import redis.asyncio\n",
    ):
        assert _hablan_con_redis(_arbol(fuente)), fuente


def test_no_confunde_el_cliente_comun_con_redis():
    fuente = (
        "from tukit_comun.cache import cliente_redis\n"
        "from tukit_comun.pruebas_redis import lo_guardado\n"
        "import redislite\n"
        "url = 'redis://localhost:6379/15'\n"
        "pytest.importorskip('pypdfium2')\n"
    )
    assert _hablan_con_redis(_arbol(fuente)) == []
