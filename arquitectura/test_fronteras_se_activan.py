"""Comprueba que los detectores de `test_fronteras.py` de verdad detectan.

Una funcion de aptitud que nunca ha fallado no esta demostrada: podria estar
midiendo nada. Como los servicios todavia no tienen codigo, las pruebas de
frontera pasan de forma vacia, asi que aqui se les da de comer una infraccion
de cada tipo y se verifica que la vean.

Cada caso reproduce un defecto REAL del sistema anterior, no uno inventado.
"""

from __future__ import annotations

import ast

from test_fronteras import (
    DUENO_DE_TABLA,
    REFERENCIAS_DECLARADAS,
    SERVICIOS,
    _buscar_ciclo,
    _columnas_declaradas,
    _modulos_importados,
    _tabla_apuntada,
    _tablas_declaradas,
)


def _arbol(fuente: str) -> ast.Module:
    return ast.parse(fuente)


# --------------------------------------------------------------------------
# Detector de importaciones entre servicios
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# Detector de tablas ajenas: el defecto original de Tukit
# --------------------------------------------------------------------------


def test_detecta_la_tabla_ajena_declarada():
    """Reproduce el defecto que origino el rediseno: dos servicios declarando
    el maestro del mismo catalogo."""
    fuente = """
class ProductoCanonico(Base):
    __tablename__ = "producto_canonico"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
"""
    declaradas = _tablas_declaradas(_arbol(fuente))
    assert declaradas, "No encontro ningun __tablename__."

    tabla, _linea = declaradas[0]
    assert DUENO_DE_TABLA[tabla] == "catalogo"
    # Si Comercio declarara esto, seria infraccion.
    assert tabla not in SERVICIOS["comercio"].tablas


def test_detecta_tabla_que_no_existe_en_el_manifiesto():
    """Una tabla inventada tampoco pasa: obliga a declararla y a pensar de
    quien es antes de crearla."""
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
    """Es la excepcion declarada: cada servicio necesita la suya local para
    escribir el evento en la misma transaccion que lo origina."""
    for servicio in SERVICIOS.values():
        if servicio.base_datos:
            assert "bandeja_salida" in servicio.tablas, (
                f"`{servicio.nombre}` tiene base propia y no declara bandeja_salida."
            )
    assert "bandeja_salida" not in DUENO_DE_TABLA, "Una tabla replicada no debe tener dueno unico."


# --------------------------------------------------------------------------
# Detector de referencias cruzadas sin declarar
# --------------------------------------------------------------------------


def test_detecta_referencia_cruzada_sin_declarar():
    """Una columna que apunta a otro dominio y no esta en el manifiesto es una
    llave foranea que Postgres no impone y que nadie escribio en ninguna parte."""
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
    # Que una devolucion apunte directo al menor es justo el tipo de referencia
    # que no debe nacer sin que alguien la mire: salta la matricula y mete un
    # dato de menor en la base transaccional.
    assert cruzadas == [("devolucion", "estudiante_id")], (
        "No detecto que `devolucion.estudiante_id` apunta a `estudiante`, de Identidad."
    )
    assert "comercio.devolucion.estudiante_id" not in REFERENCIAS_DECLARADAS


def test_detecta_la_columna_de_actor_que_no_termina_en_id():
    """El hueco que esta prueba cierra es de la prueba misma, no del codigo.

    El detector solo miraba el sufijo `_id`, asi que `curado_por`,
    `resuelta_por` y `publicada_por` cruzaban a `identidad.usuario` sin que
    nada se quejara. Tres referencias reales pasaron por ahi.

    Es el modo de falla propio de una prueba de arquitectura: no grita un
    falso positivo, se queda callada, y uno cree que la frontera esta
    vigilada cuando no lo esta. Por eso la comprobacion nueva necesita su
    propia prueba de que dispara.
    """
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
    """`creado_en` y `nombre` no apuntan a nada. Si el detector las marcara,
    el manifiesto se llenaria de ruido y dejaria de leerse."""
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
    """`linea_pedido.pedido_id` es local a Comercio: no es referencia cruzada."""
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
    """Una clase de Pydantic o una dataclass no declara tabla y no debe
    producir falsos positivos."""
    fuente = """
class RespuestaPedido(BaseModel):
    matricula_id: uuid.UUID
"""
    assert _columnas_declaradas(_arbol(fuente)) == []


# --------------------------------------------------------------------------
# Detector de ciclos entre servicios
# --------------------------------------------------------------------------


def test_detecta_el_ciclo_real_que_existio():
    """El ciclo que de verdad estuvo en el manifiesto, no uno inventado.

    Catalogo referenciaba `operacion.caso` desde su tabla de tareas de
    importacion, y Operacion referencia a Catalogo. Una sola columna bastaba.
    """
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
    """Que tres servicios apunten todos a Identidad no es un ciclo.

    Es el caso normal del sistema, y un detector que lo marcara volveria la
    prueba inservible desde el primer dia.
    """
    grafo = {
        "identidad": set(),
        "catalogo": {"identidad"},
        "comercio": {"identidad", "catalogo"},
        "inteligencia": {"identidad", "catalogo"},
    }
    assert _buscar_ciclo(grafo) is None


def test_detecta_el_ciclo_largo_y_no_solo_el_de_dos():
    """Un ciclo de tres es mas facil de introducir sin darse cuenta, porque
    ningun par de servicios se referencia mutuamente de forma visible."""
    grafo = {
        "identidad": {"comercio"},
        "catalogo": {"identidad"},
        "comercio": {"catalogo"},
    }
    ciclo = _buscar_ciclo(grafo)
    assert ciclo is not None
    assert len(set(ciclo)) == 3


def test_un_servicio_que_se_referencia_a_si_mismo_no_cuenta():
    """Una llave foranea dentro de la misma base es normal y fisica."""
    assert _buscar_ciclo({"catalogo": {"catalogo"}, "identidad": set()}) is None
