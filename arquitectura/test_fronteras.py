"""Funciones de aptitud: verifican que el codigo respete las fronteras declaradas.

En el sentido de Ford, Parsons y Kua, una funcion de aptitud es una prueba
automatica y continua sobre una caracteristica arquitectonica. Estas cuatro son
la diferencia entre *afirmar* que Tukit tiene contextos delimitados y
*demostrarlo* en cada integracion.

Existen porque el defecto mas grave del sistema anterior, dos servicios
declarando el maestro del mismo catalogo, no se produjo por falta de criterio
sino porque nada verificaba el criterio. La disciplina humana ya fallo una vez
en este proyecto; esta es la defensa que no depende de ella.

Van ANTES de mover la primera tabla, para que el movimiento trace las fronteras
en vez de borrarlas. Ver ADR 0014.

Ejecutar:  pytest arquitectura/ -v
"""

from __future__ import annotations

import ast
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
MANIFIESTO = RAIZ / "arquitectura" / "manifiesto.toml"


# --------------------------------------------------------------------------
# Carga del manifiesto
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Servicio:
    nombre: str
    lenguaje: str
    ruta: Path
    paquete: str
    base_datos: str
    tablas: frozenset[str]


def _cargar():
    datos = tomllib.loads(MANIFIESTO.read_text(encoding="utf-8"))
    servicios = {
        nombre: Servicio(
            nombre=nombre,
            lenguaje=cfg["lenguaje"],
            ruta=RAIZ / cfg["ruta"],
            paquete=cfg["paquete"],
            base_datos=cfg["base_datos"],
            tablas=frozenset(cfg["tablas"]),
        )
        for nombre, cfg in datos["servicios"].items()
    }
    return datos, servicios


DATOS, SERVICIOS = _cargar()
REPLICADAS = frozenset(DATOS["meta"]["tablas_replicadas"])
REFERENCIAS_DECLARADAS = frozenset(ref["desde"] for ref in DATOS.get("referencias_cruzadas", []))

# Tabla -> servicio duenno. Las replicadas no entran: son de todos por diseno.
DUENO_DE_TABLA: dict[str, str] = {
    tabla: servicio.nombre
    for servicio in SERVICIOS.values()
    for tabla in servicio.tablas
    if tabla not in REPLICADAS
}


def _archivos_python(servicio: Servicio) -> list[Path]:
    if not servicio.ruta.exists():
        return []
    return [
        ruta
        for ruta in servicio.ruta.rglob("*.py")
        if ".venv" not in ruta.parts and "__pycache__" not in ruta.parts
    ]


def _arbol(ruta: Path) -> ast.Module | None:
    try:
        return ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    except SyntaxError:
        pytest.fail(f"{ruta.relative_to(RAIZ)} no es Python valido y no se pudo analizar.")
        return None


def _relativa(ruta: Path) -> str:
    return str(ruta.relative_to(RAIZ))


# --------------------------------------------------------------------------
# Coherencia del propio manifiesto
# --------------------------------------------------------------------------


def test_el_manifiesto_cuadra_con_el_esquema_objetivo():
    """Si el manifiesto se desincroniza del diseno, las demas pruebas validan
    contra una frontera equivocada y dan una falsa sensacion de seguridad."""
    total = sum(len(s.tablas) for s in SERVICIOS.values())
    esperado = DATOS["meta"]["total_tablas_esperado"]
    assert total == esperado, (
        f"El manifiesto declara {total} tablas y el esquema objetivo define {esperado}.\n"
        f"Si agregaste o quitaste una tabla a proposito, actualiza tambien "
        f"`total_tablas_esperado` y Arquitectura/ESQUEMA_OBJETIVO.md."
    )


def test_las_referencias_cruzadas_declaradas_apuntan_a_algo_real():
    """Una referencia mal escrita en el manifiesto es peor que no declararla:
    la prueba de la regla 4 la da por buena y deja pasar la infraccion que
    debia atrapar."""
    problemas: list[str] = []

    for ref in DATOS.get("referencias_cruzadas", []):
        desde, hacia = ref["desde"], ref["hacia"]

        partes = desde.split(".")
        if len(partes) != 3:
            problemas.append(f"  `{desde}` no tiene la forma servicio.tabla.columna")
            continue
        servicio, tabla, columna = partes

        if servicio not in SERVICIOS:
            problemas.append(f"  `{desde}`: el servicio `{servicio}` no existe")
        elif tabla not in SERVICIOS[servicio].tablas:
            problemas.append(f"  `{desde}`: `{tabla}` no es una tabla de `{servicio}`")
        if _tabla_apuntada(columna) is None:
            problemas.append(f"  `{desde}`: la columna no termina en `_id` ni en `_por`")

        destino = hacia.split(".")
        if len(destino) != 2:
            problemas.append(f"  `{hacia}` no tiene la forma servicio.tabla")
            continue
        servicio_destino, tabla_destino = destino

        if servicio_destino not in SERVICIOS:
            problemas.append(f"  `{hacia}`: el servicio `{servicio_destino}` no existe")
        elif tabla_destino not in SERVICIOS[servicio_destino].tablas:
            problemas.append(f"  `{hacia}`: `{tabla_destino}` no es tabla de `{servicio_destino}`")
        elif servicio_destino == servicio:
            problemas.append(
                f"  `{desde}` -> `{hacia}`: es referencia LOCAL, no cruzada. "
                f"Debe ser una llave foranea de verdad, no una declaracion."
            )

    assert not problemas, "Referencias cruzadas mal declaradas:\n" + "\n".join(problemas)


def test_ninguna_tabla_tiene_dos_duenos():
    """Es exactamente el defecto que origino todo el rediseno: `productos_catalogo`
    declarada como maestro en MS-Comercio y en MS-Busqueda a la vez."""
    apariciones: dict[str, list[str]] = {}
    for servicio in SERVICIOS.values():
        for tabla in servicio.tablas:
            apariciones.setdefault(tabla, []).append(servicio.nombre)

    duplicadas = {
        tabla: duenos for tabla, duenos in apariciones.items() if len(duenos) > 1 and tabla not in REPLICADAS
    }
    assert not duplicadas, (
        "Hay tablas declaradas por mas de un servicio sin estar en "
        "`tablas_replicadas`:\n"
        + "\n".join(f"  {t}: {', '.join(d)}" for t, d in sorted(duplicadas.items()))
        + "\n\nDos duenos de la misma tabla significa que no hay dueno. Elige uno, "
        "o declarala replicada y justifica por que cada copia es necesaria."
    )


# --------------------------------------------------------------------------
# Regla 1: ningun servicio importa codigo de otro servicio
# --------------------------------------------------------------------------


def _modulos_importados(arbol: ast.Module) -> set[str]:
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            modulos.add(nodo.module)
    return modulos


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_ningun_servicio_importa_otro_servicio(nombre: str):
    """Un servicio solo puede importar de `libs/`. Importar el codigo de otro
    servicio convierte dos desplegables en uno acoplado a nivel de compilacion,
    y la separacion pasa a ser decorativa."""
    servicio = SERVICIOS[nombre]
    ajenos = {s.paquete: s.nombre for s in SERVICIOS.values() if s.nombre != nombre}

    infracciones: list[str] = []
    for ruta in _archivos_python(servicio):
        arbol = _arbol(ruta)
        if arbol is None:
            continue
        for modulo in _modulos_importados(arbol):
            raiz = modulo.split(".")[0]
            if raiz in ajenos:
                infracciones.append(f"  {_relativa(ruta)} importa `{modulo}` (de {ajenos[raiz]})")

    assert not infracciones, (
        f"El servicio `{nombre}` importa codigo de otro servicio:\n"
        + "\n".join(sorted(infracciones))
        + "\n\nLo compartido va en `libs/`. Lo que necesitas del otro dominio se "
        "pide por HTTP o llega por evento."
    )


# --------------------------------------------------------------------------
# Regla 2: ningun servicio declara una tabla de un dominio ajeno
# --------------------------------------------------------------------------


def _tablas_declaradas(arbol: ast.Module) -> list[tuple[str, int]]:
    """Busca `__tablename__ = "x"` en cualquier clase del modulo."""
    encontradas: list[tuple[str, int]] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign):
            continue
        for destino in nodo.targets:
            if (
                isinstance(destino, ast.Name)
                and destino.id == "__tablename__"
                and isinstance(nodo.value, ast.Constant)
                and isinstance(nodo.value.value, str)
            ):
                encontradas.append((nodo.value.value, nodo.lineno))
    return encontradas


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_ningun_servicio_declara_tabla_ajena(nombre: str):
    """La regla que habria impedido el defecto original.

    Declarar el modelo de una tabla ajena es como nace un segundo maestro: al
    principio es "solo para leer", y termina escribiendo.
    """
    servicio = SERVICIOS[nombre]
    infracciones: list[str] = []

    for ruta in _archivos_python(servicio):
        arbol = _arbol(ruta)
        if arbol is None:
            continue
        for tabla, linea in _tablas_declaradas(arbol):
            if tabla in servicio.tablas:
                continue
            dueno = DUENO_DE_TABLA.get(tabla)
            if dueno:
                infracciones.append(f"  {_relativa(ruta)}:{linea} declara `{tabla}`, que pertenece a {dueno}")
            else:
                infracciones.append(
                    f"  {_relativa(ruta)}:{linea} declara `{tabla}`, que no esta en el manifiesto"
                )

    assert not infracciones, (
        f"El servicio `{nombre}` declara tablas que no le pertenecen:\n"
        + "\n".join(sorted(infracciones))
        + "\n\nSi de verdad necesitas ese dato, pidelo por HTTP o suscribete al "
        "evento. Si la tabla es nueva y es tuya, agregala al manifiesto."
    )


# --------------------------------------------------------------------------
# Regla 3: ningun servicio se conecta a la base de otro
# --------------------------------------------------------------------------


def _docstrings(arbol: ast.Module) -> set[int]:
    """Ids (por identidad de nodo) de los `ast.Constant` que son docstrings.

    Un docstring es el primer enunciado de un modulo, clase o funcion cuando es
    un literal de cadena. Es prosa, no codigo: nombrar ahi el paquete de un
    servicio hermano —`tukit_operacion.repartidor`, que describe quien drena la
    bandeja— es correcto y deseable, no una conexion a su base.
    """
    ids: set[int] = set()
    for nodo in ast.walk(arbol):
        cuerpo = getattr(nodo, "body", None)
        if not isinstance(cuerpo, list) or not cuerpo:
            continue
        if not isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        primero = cuerpo[0]
        if (
            isinstance(primero, ast.Expr)
            and isinstance(primero.value, ast.Constant)
            and isinstance(primero.value.value, str)
        ):
            ids.add(id(primero.value))
    return ids


def _cadenas_no_docstring(arbol: ast.Module) -> list[str]:
    """Valores de todos los literales de cadena del modulo MENOS los docstrings.

    La base de un servicio nunca se escribe como literal: `crear_motor` la
    deriva del entorno (`bd.py`, "El servicio no escribe el nombre de su base
    como literal"). Por eso una conexion a la base ajena solo puede aparecer
    como un literal de cadena real —una URL de conexion incrustada—, no como
    prosa. Los comentarios ni siquiera estan en el arbol, asi que se excluyen
    solos; aqui se quitan ademas los docstrings.
    """
    saltar = _docstrings(arbol)
    cadenas: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in saltar:
            cadenas.append(nodo.value)
    return cadenas


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_ningun_servicio_nombra_la_base_de_otro(nombre: str):
    """Una base por servicio. Conectarse a la base ajena salta la frontera
    entera sin pasar por ninguna interfaz, y ninguna de las otras reglas lo ve.

    El detector busca el nombre de la base ajena en los literales de cadena del
    codigo (donde viviria una URL de conexion incrustada), no en la linea cruda:
    la convencion `tukit_<servicio>` hace que el nombre del paquete de un
    servicio y el de su base coincidan, y un servicio SI puede —y debe— nombrar
    el paquete hermano en un docstring o comentario (para decir quien drena su
    bandeja). Mirar la linea cruda confundia esa prosa con una conexion. Se mira
    solo el AST, sin docstrings, para separar el codigo de la documentacion.
    """
    servicio = SERVICIOS[nombre]
    ajenas = {s.base_datos: s.nombre for s in SERVICIOS.values() if s.nombre != nombre and s.base_datos}
    if not ajenas:
        pytest.skip("No hay otras bases declaradas.")

    infracciones: list[str] = []
    for ruta in _archivos_python(servicio):
        arbol = _arbol(ruta)
        if arbol is None:
            continue
        cadenas = _cadenas_no_docstring(arbol)
        for base, dueno in ajenas.items():
            if any(base in cadena for cadena in cadenas):
                infracciones.append(f"  {_relativa(ruta)} menciona la base `{base}` (de {dueno})")

    assert not infracciones, f"El servicio `{nombre}` nombra la base de datos de otro:\n" + "\n".join(
        sorted(infracciones)
    )


# --------------------------------------------------------------------------
# Regla 3b: las lecturas cruzadas son solo el respaldo sin broker
# --------------------------------------------------------------------------

LECTURAS_CRUZADAS: dict[str, dict] = {
    lectura["modulo"]: lectura for lectura in DATOS.get("lecturas_cruzadas", [])
}
# La funcion con la que un servicio abre la base de otro. La propia se abre con
# `crear_motor`, que no admite otro nombre que el del servicio.
ABRE_BASE_AJENA = "url_desde_entorno"
# Por donde entran los eventos con RabbitMQ en un modulo con lectura cruzada.
ENTRADA_CON_BROKER = "escuchar_cola"
TOPOLOGIA = RAIZ / "libs" / "py" / "tukit_comun" / "tukit_comun" / "topologia.py"


def _modulo_de(servicio: Servicio, ruta: Path) -> str:
    return ".".join(ruta.relative_to(servicio.ruta).with_suffix("").parts)


def _llama(nodo: ast.AST, nombre: str) -> bool:
    """Si dentro de `nodo` hay una llamada a `nombre`, como funcion o como metodo."""
    for hijo in ast.walk(nodo):
        if isinstance(hijo, ast.Call):
            funcion = hijo.func
            if isinstance(funcion, ast.Name) and funcion.id == nombre:
                return True
            if isinstance(funcion, ast.Attribute) and funcion.attr == nombre:
                return True
    return False


def _funciones(arbol: ast.Module) -> dict[str, list[ast.AST]]:
    """Las funciones y metodos del modulo, por nombre."""
    funciones: dict[str, list[ast.AST]] = {}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funciones.setdefault(nodo.name, []).append(nodo)
    return funciones


def _alcanzables(arbol: ast.Module, desde: str) -> set[str]:
    """Las funciones del modulo a las que se llega desde `desde`, ella incluida.

    Se sigue por nombre y sin tipos: cualquier mencion cuenta, llamada o no,
    porque un manejador viaja como valor (`manejar=poller.manejar`,
    `functools.partial(atender_aviso, ...)`). Y `self.manejar` cuenta como
    cualquier `manejar` del modulo. Sobra antes que faltar: un falso positivo
    se ve, uno negativo no."""
    funciones = _funciones(arbol)
    vistas: set[str] = set()
    pendientes = [desde]
    while pendientes:
        nombre = pendientes.pop()
        if nombre in vistas or nombre not in funciones:
            continue
        vistas.add(nombre)
        for definicion in funciones[nombre]:
            for hijo in ast.walk(definicion):
                if isinstance(hijo, ast.Name):
                    pendientes.append(hijo.id)
                elif isinstance(hijo, ast.Attribute):
                    pendientes.append(hijo.attr)
    return vistas


def _colas_de_la_topologia() -> set[str]:
    """Los nombres de las colas que declara `tukit_comun.topologia`, leidos del
    AST: esta prueba corre sin las dependencias de la libreria."""
    arbol = ast.parse(TOPOLOGIA.read_text(encoding="utf-8"))
    return {
        nodo.args[0].value
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Name)
        and nodo.func.id == "Cola"
        and nodo.args
        and isinstance(nodo.args[0], ast.Constant)
        and isinstance(nodo.args[0].value, str)
    }


def _revisar_lectura_cruzada(modulo: str, arbol: ast.Module, declarada: dict | None) -> list[str]:
    """Lo que esta mal en un modulo que abre la base de otro servicio, o nada.

    Tiene que estar declarado con `modo = "sin_broker"`, tener `escuchar_cola`
    (por donde le llegan los eventos con RabbitMQ) y no llegar desde ahi a
    ninguna funcion que abra una base ajena."""
    if declarada is None:
        return [f"`{modulo}` abre la base de otro servicio y no esta en `[[lecturas_cruzadas]]`"]
    problemas: list[str] = []
    if declarada.get("modo") != "sin_broker":
        problemas.append(f'`{modulo}` declara `modo = {declarada.get("modo")!r}`; solo vale "sin_broker"')
    alcanzadas = _alcanzables(arbol, ENTRADA_CON_BROKER)
    if not alcanzadas:
        problemas.append(f"`{modulo}` no tiene `{ENTRADA_CON_BROKER}`: con broker no recibe sus eventos")
    funciones = _funciones(arbol)
    lectoras = sorted(
        nombre
        for nombre in alcanzadas
        if any(_llama(definicion, ABRE_BASE_AJENA) for definicion in funciones[nombre])
    )
    if lectoras:
        problemas.append(
            f"`{modulo}.{ENTRADA_CON_BROKER}` llega a una lectura cruzada por {', '.join(lectoras)}"
        )
    return problemas


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_toda_lectura_cruzada_es_respaldo_sin_broker(nombre: str):
    """Con RabbitMQ, ningun servicio lee la base de otro (ADR 0046).

    La regla 3 no ve estas lecturas: el nombre de la base lo deriva la
    libreria. Esta las encuentra por `url_desde_entorno`, exige que esten
    declaradas como respaldo sin broker y que el camino con broker
    (`escuchar_cola`) no llegue a ellas."""
    servicio = SERVICIOS[nombre]
    infracciones: list[str] = []
    for ruta in _archivos_python(servicio):
        arbol = _arbol(ruta)
        if arbol is None or not _llama(arbol, ABRE_BASE_AJENA):
            continue
        modulo = _modulo_de(servicio, ruta)
        infracciones += [
            f"  {p}" for p in _revisar_lectura_cruzada(modulo, arbol, LECTURAS_CRUZADAS.get(modulo))
        ]

    assert not infracciones, (
        f"El servicio `{nombre}` lee la base de otro fuera del respaldo sin broker:\n"
        + "\n".join(sorted(infracciones))
        + "\n\nCon RabbitMQ los eventos llegan por la cola del consumidor. Si de verdad "
        "hace falta leer la base ajena sin broker, declaralo en `[[lecturas_cruzadas]]`."
    )


def test_las_lecturas_cruzadas_declaradas_existen():
    """Una declaracion que ya no corresponde a nada es una excepcion abierta
    que nadie usa, y la siguiente lectura cruzada entraria por ella."""
    colas = _colas_de_la_topologia()
    problemas: list[str] = []
    for modulo, lectura in sorted(LECTURAS_CRUZADAS.items()):
        servicio = SERVICIOS.get(lectura.get("desde", ""))
        if servicio is None:
            problemas.append(f"  `{modulo}`: `desde = {lectura.get('desde')!r}` no es un servicio")
            continue
        ruta = servicio.ruta.joinpath(*modulo.split(".")).with_suffix(".py")
        if not ruta.exists():
            problemas.append(f"  `{modulo}`: no existe {_relativa(ruta)}")
        elif not _llama(ast.parse(ruta.read_text(encoding="utf-8")), ABRE_BASE_AJENA):
            problemas.append(f"  `{modulo}` ya no abre ninguna base ajena: borra la declaracion")
        hacia = lectura.get("hacia", [])
        if not hacia or any(h not in SERVICIOS or h == servicio.nombre for h in hacia):
            problemas.append(f"  `{modulo}`: `hacia = {hacia!r}` tiene que nombrar otros servicios")
        if lectura.get("cola") not in colas:
            problemas.append(
                f"  `{modulo}`: la cola {lectura.get('cola')!r} no esta en `tukit_comun.topologia`"
            )

    assert not problemas, "Lecturas cruzadas mal declaradas:\n" + "\n".join(problemas)


# --------------------------------------------------------------------------
# Regla 4: toda referencia a otro dominio esta declarada
# --------------------------------------------------------------------------


def _columnas_declaradas(arbol: ast.Module) -> list[tuple[str, str, int]]:
    """Devuelve (tabla, columna, linea) de cada `x: Mapped[...] = mapped_column(...)`
    dentro de una clase que declare `__tablename__`."""
    resultado: list[tuple[str, str, int]] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.ClassDef):
            continue
        tabla = None
        for cuerpo in nodo.body:
            if isinstance(cuerpo, ast.Assign):
                for destino in cuerpo.targets:
                    if (
                        isinstance(destino, ast.Name)
                        and destino.id == "__tablename__"
                        and isinstance(cuerpo.value, ast.Constant)
                    ):
                        tabla = cuerpo.value.value
        if not tabla:
            continue
        for cuerpo in nodo.body:
            if isinstance(cuerpo, ast.AnnAssign) and isinstance(cuerpo.target, ast.Name):
                resultado.append((tabla, cuerpo.target.id, cuerpo.lineno))
    return resultado


def _tabla_apuntada(columna: str) -> str | None:
    """Que tabla referencia una columna, segun como se llame.

    Dos convenciones, no una. `x_id` apunta a la tabla `x`, y `x_por` apunta
    a `usuario` porque nombra a quien hizo algo: `curado_por`, `resuelta_por`,
    `publicada_por`.

    La segunda se agrego despues de que esta misma prueba dejara pasar tres
    referencias a `identidad.usuario` en Catalogo. El detector solo miraba el
    sufijo `_id`, asi que una columna de actor cruzaba de servicio sin que
    nada se quejara. Vale la pena anotarlo porque es el modo de falla propio
    de una prueba de arquitectura: no da un falso positivo ruidoso, se queda
    callada, y uno cree que la frontera esta vigilada cuando no lo esta.
    """
    if columna.endswith("_id"):
        return columna[:-3]
    if columna.endswith("_por"):
        return "usuario"
    return None


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_toda_referencia_a_otro_dominio_esta_declarada(nombre: str):
    """Una columna `x_id` o `x_por` que apunta a una tabla de otro servicio es
    una llave foranea que Postgres no puede imponer. Si ademas no esta escrita
    en ningun lado, es invisible: nadie sabe que existe hasta que rompe.

    Es exactamente lo que pasaba con `kits_optimizados.items`, un JSON con
    `producto_id` adentro que para Postgres era texto.
    """
    servicio = SERVICIOS[nombre]
    sin_declarar: list[str] = []

    for ruta in _archivos_python(servicio):
        arbol = _arbol(ruta)
        if arbol is None:
            continue
        for tabla, columna, linea in _columnas_declaradas(arbol):
            apuntada = _tabla_apuntada(columna)
            if apuntada is None:
                continue
            dueno = DUENO_DE_TABLA.get(apuntada)
            if dueno is None or dueno == nombre:
                continue
            clave = f"{nombre}.{tabla}.{columna}"
            if clave not in REFERENCIAS_DECLARADAS:
                sin_declarar.append(
                    f"  {_relativa(ruta)}:{linea} -> `{clave}` apunta a `{apuntada}` de {dueno}"
                )

    assert not sin_declarar, (
        f"El servicio `{nombre}` referencia otro dominio sin declararlo:\n"
        + "\n".join(sorted(sin_declarar))
        + "\n\nAgregalas a `[[referencias_cruzadas]]` en el manifiesto, con la nota "
        "de como se valida la integridad que Postgres ya no puede imponer."
    )


# --------------------------------------------------------------------------
# Regla 5: el lenguaje declarado es el que hay
# --------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_el_lenguaje_declarado_coincide_con_el_codigo(nombre: str):
    """El reparto de lenguajes salio de una medicion (ver
    Arquitectura/PERFILADO_PIPELINE.md). Si alguien mete Go donde el manifiesto
    dice Python, o al reves, la decision cambio sin que nadie la revisara."""
    servicio = SERVICIOS[nombre]
    if not servicio.ruta.exists():
        pytest.skip(f"`{nombre}` todavia no tiene codigo.")

    hay_python = bool(_archivos_python(servicio))
    hay_go = any(ruta for ruta in servicio.ruta.rglob("*.go") if "vendor" not in ruta.parts)

    if servicio.lenguaje == "python":
        assert not hay_go, (
            f"`{nombre}` esta declarado en Python y tiene archivos .go.\n"
            f"Si el cambio es deliberado, actualiza el manifiesto y escribe el ADR "
            f"que lo justifique con mediciones."
        )
    elif servicio.lenguaje == "go":
        assert not hay_python, f"`{nombre}` esta declarado en Go y tiene archivos .py."


def _grafo_de_dependencias() -> dict[str, set[str]]:
    """Que servicio referencia a que otro, segun el manifiesto."""
    grafo: dict[str, set[str]] = {n: set() for n in SERVICIOS}
    for ref in DATOS.get("referencias_cruzadas", []):
        origen = ref["desde"].split(".")[0]
        destino = ref["hacia"].split(".")[0]
        if origen in grafo and destino != origen:
            grafo[origen].add(destino)
    return grafo


def _buscar_ciclo(grafo: dict[str, set[str]]) -> list[str] | None:
    """Devuelve un ciclo concreto, no solo si existe.

    Decir "hay un ciclo" no sirve para arreglarlo; hay que decir cual.
    """
    EN_CAMINO, LISTO = 1, 2
    estado: dict[str, int] = {}
    camino: list[str] = []

    def visitar(nodo: str) -> list[str] | None:
        estado[nodo] = EN_CAMINO
        camino.append(nodo)
        for vecino in sorted(grafo.get(nodo, ())):
            # Una arista de un servicio consigo mismo es una llave foranea
            # fisica dentro de su propia base. No afecta el orden de arranque
            # ni el de restauracion, asi que no es un ciclo en el sentido que
            # aqui importa.
            if vecino == nodo:
                continue
            if estado.get(vecino) == EN_CAMINO:
                return camino[camino.index(vecino) :] + [vecino]
            if estado.get(vecino) is None:
                encontrado = visitar(vecino)
                if encontrado:
                    return encontrado
        camino.pop()
        estado[nodo] = LISTO
        return None

    for nodo in sorted(grafo):
        if estado.get(nodo) is None:
            ciclo = visitar(nodo)
            if ciclo:
                return ciclo
    return None


def test_el_grafo_de_dependencias_entre_servicios_es_aciclico():
    """Ningun ciclo de referencias entre servicios.

    Esta prueba se agrego despues de que una sola columna, `caso_id` en la
    tabla de tareas de importacion de Catalogo, metiera una arista hacia
    Operacion cuando todas las demas van hacia Identidad y Catalogo. Bastaba
    esa para cerrar el ciclo.

    Lo que se pierde con un ciclo no es elegancia. Se pierde el **orden de
    arranque** (cual servicio puede levantar primero sin que le falte algo) y
    el **orden de restauracion** (en que secuencia devolver los respaldos para
    que las referencias resuelvan). Con un ciclo, ninguno de los dos existe, y
    eso solo se descubre el dia que hay que restaurar.

    La direccion correcta cuando aparece una arista prohibida casi siempre es
    invertirla usando la bandeja de salida: en vez de que A guarde el
    identificador de algo de B, A publica un hecho y B reacciona apuntando de
    vuelta.
    """
    ciclo = _buscar_ciclo(_grafo_de_dependencias())
    assert ciclo is None, (
        "El grafo de dependencias entre servicios tiene un ciclo:\n"
        f"  {' -> '.join(ciclo)}\n\n"
        "Invierte una de las aristas con la bandeja de salida: el servicio de "
        "origen publica el hecho y el de destino reacciona, en vez de guardar "
        "el identificador del otro dominio."
    )


# --------------------------------------------------------------------------
# Regla 6: solo `tukit_comun` habla con Redis
# --------------------------------------------------------------------------

COMUN = RAIZ / "libs" / "py" / "tukit_comun"
# Donde hay Python que no es `tukit_comun`: los servicios, sus pruebas incluidas,
# los ensayos, las otras librerias y estas mismas pruebas.
CON_PYTHON = ("servicios", "ensayos", "libs", "arquitectura", "datos")
# Las llamadas que importan un modulo por su nombre.
IMPORTAN_POR_NOMBRE = frozenset({"importorskip", "import_module", "__import__"})


def _nombre_llamado(funcion: ast.expr) -> str | None:
    if isinstance(funcion, ast.Name):
        return funcion.id
    if isinstance(funcion, ast.Attribute):
        return funcion.attr
    return None


def _hablan_con_redis(arbol: ast.Module) -> list[tuple[str, int]]:
    """Lo que trae `redis` en un modulo, con su linea: los `import`, y las
    llamadas como `pytest.importorskip("redis.asyncio")`."""

    def de_redis(modulo: str) -> bool:
        return modulo.split(".")[0] == "redis"

    encontrados: list[tuple[str, int]] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            encontrados += [(alias.name, nodo.lineno) for alias in nodo.names if de_redis(alias.name)]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0 and de_redis(nodo.module):
            encontrados.append((nodo.module, nodo.lineno))
        elif (
            isinstance(nodo, ast.Call)
            and _nombre_llamado(nodo.func) in IMPORTAN_POR_NOMBRE
            and nodo.args
            and isinstance(nodo.args[0], ast.Constant)
            and isinstance(nodo.args[0].value, str)
            and de_redis(nodo.args[0].value)
        ):
            encontrados.append((nodo.args[0].value, nodo.lineno))
    return encontrados


def _python_fuera_de_comun() -> list[Path]:
    fuera = {".venv", "__pycache__", "node_modules"}
    return [
        ruta
        for carpeta in CON_PYTHON
        for ruta in (RAIZ / carpeta).rglob("*.py")
        if not fuera & set(ruta.parts) and not ruta.is_relative_to(COMUN)
    ]


def test_solo_tukit_comun_habla_con_redis():
    """Redis es cache y contador, nunca la unica copia de nada (ADR 0047), y lo
    que lo hace opcional vive en un solo sitio: `tukit_comun.cache`, con su
    espera corta, su pausa tras un fallo y su conteo en memoria. Un servicio
    que importara `redis` por su cuenta se saltaria todo eso y se caeria con
    Redis. Las pruebas tampoco: miran lo guardado con
    `tukit_comun.pruebas_redis`."""
    infracciones = [
        f"  {_relativa(ruta)}:{linea} trae `{modulo}`"
        for ruta in _python_fuera_de_comun()
        if (arbol := _arbol(ruta)) is not None
        for modulo, linea in _hablan_con_redis(arbol)
    ]

    assert not infracciones, (
        "Fuera de `tukit_comun` hay codigo que habla con Redis directo:\n"
        + "\n".join(sorted(infracciones))
        + "\n\nUsa `tukit_comun.cache.cliente_redis()`, y en las pruebas "
        "`tukit_comun.pruebas_redis`."
    )
