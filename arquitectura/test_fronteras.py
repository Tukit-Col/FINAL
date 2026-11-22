"""Funciones de aptitud: verifican que el codigo respete las fronteras declaradas en el manifiesto.

Decisiones:
- Las fronteras son pruebas automaticas y no una convencion: si el codigo se sale de lo
  declarado en `arquitectura/manifiesto.toml`, la integracion falla.
- Cada regla tiene su contraparte en `test_fronteras_se_activan.py`, que le da de comer una
  infraccion y comprueba que la detecte.

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


@dataclass(frozen=True)
class Servicio:
    nombre: str
    ruta: Path
    paquete: str
    base_datos: str
    tablas: frozenset[str]


def _cargar():
    datos = tomllib.loads(MANIFIESTO.read_text(encoding="utf-8"))
    servicios = {
        nombre: Servicio(
            nombre=nombre,
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


def test_el_manifiesto_cuadra_con_el_esquema_objetivo():
    total = sum(len(s.tablas) for s in SERVICIOS.values())
    esperado = DATOS["meta"]["total_tablas_esperado"]
    assert total == esperado, (
        f"El manifiesto declara {total} tablas y el esquema objetivo define {esperado}.\n"
        f"Si agregaste o quitaste una tabla a proposito, actualiza tambien "
        f"`total_tablas_esperado` y Arquitectura/ESQUEMA_OBJETIVO.md."
    )


def test_las_referencias_cruzadas_declaradas_apuntan_a_algo_real():
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


def _tablas_declaradas(arbol: ast.Module) -> list[tuple[str, int]]:
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


def _docstrings(arbol: ast.Module) -> set[int]:
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
    saltar = _docstrings(arbol)
    cadenas: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in saltar:
            cadenas.append(nodo.value)
    return cadenas


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_ningun_servicio_nombra_la_base_de_otro(nombre: str):
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


LECTURAS_CRUZADAS: dict[str, dict] = {
    lectura["modulo"]: lectura for lectura in DATOS.get("lecturas_cruzadas", [])
}
ABRE_BASE_AJENA = "url_desde_entorno"
ENTRADA_CON_BROKER = "escuchar_cola"
TOPOLOGIA = RAIZ / "libs" / "py" / "tukit_comun" / "tukit_comun" / "topologia.py"


def _modulo_de(servicio: Servicio, ruta: Path) -> str:
    return ".".join(ruta.relative_to(servicio.ruta).with_suffix("").parts)


def _llama(nodo: ast.AST, nombre: str) -> bool:
    for hijo in ast.walk(nodo):
        if isinstance(hijo, ast.Call):
            funcion = hijo.func
            if isinstance(funcion, ast.Name) and funcion.id == nombre:
                return True
            if isinstance(funcion, ast.Attribute) and funcion.attr == nombre:
                return True
    return False


def _funciones(arbol: ast.Module) -> dict[str, list[ast.AST]]:
    funciones: dict[str, list[ast.AST]] = {}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funciones.setdefault(nodo.name, []).append(nodo)
    return funciones


def _alcanzables(arbol: ast.Module, desde: str) -> set[str]:
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


def _columnas_declaradas(arbol: ast.Module) -> list[tuple[str, str, int]]:
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
    if columna.endswith("_id"):
        return columna[:-3]
    if columna.endswith("_por"):
        return "usuario"
    return None


@pytest.mark.parametrize("nombre", sorted(SERVICIOS))
def test_toda_referencia_a_otro_dominio_esta_declarada(nombre: str):
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


def _grafo_de_dependencias() -> dict[str, set[str]]:
    grafo: dict[str, set[str]] = {n: set() for n in SERVICIOS}
    for ref in DATOS.get("referencias_cruzadas", []):
        origen = ref["desde"].split(".")[0]
        destino = ref["hacia"].split(".")[0]
        if origen in grafo and destino != origen:
            grafo[origen].add(destino)
    return grafo


def _buscar_ciclo(grafo: dict[str, set[str]]) -> list[str] | None:
    EN_CAMINO, LISTO = 1, 2
    estado: dict[str, int] = {}
    camino: list[str] = []

    def visitar(nodo: str) -> list[str] | None:
        estado[nodo] = EN_CAMINO
        camino.append(nodo)
        for vecino in sorted(grafo.get(nodo, ())):
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
    ciclo = _buscar_ciclo(_grafo_de_dependencias())
    assert ciclo is None, (
        "El grafo de dependencias entre servicios tiene un ciclo:\n"
        f"  {' -> '.join(ciclo)}\n\n"
        "Invierte una de las aristas con la bandeja de salida: el servicio de "
        "origen publica el hecho y el de destino reacciona, en vez de guardar "
        "el identificador del otro dominio."
    )


COMUN = RAIZ / "libs" / "py" / "tukit_comun"
CON_PYTHON = ("servicios", "ensayos", "libs", "arquitectura", "datos")
IMPORTAN_POR_NOMBRE = frozenset({"importorskip", "import_module", "__import__"})


def _nombre_llamado(funcion: ast.expr) -> str | None:
    if isinstance(funcion, ast.Name):
        return funcion.id
    if isinstance(funcion, ast.Attribute):
        return funcion.attr
    return None


def _hablan_con_redis(arbol: ast.Module) -> list[tuple[str, int]]:

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
